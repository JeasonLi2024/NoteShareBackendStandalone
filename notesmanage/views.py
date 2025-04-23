import os, shutil, json, requests
import tempfile
import subprocess
from django.conf import settings
import uuid
from PIL import Image
from user.models import PointHistory
from .utils import extract_keywords, generate_cover_images, compress_image
from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from notifications.models import Notification
from .models import Note, Comment, Like, TopNote, Favorite, DraftNote, NoteImage, NoteFile
from .pagination import SubCommentPagination, RootCommentPagination
from django.core.paginator import Paginator
from rest_framework.pagination import PageNumberPagination
from .serializers import(
    NoteSerializer, CommentSerializer, NoteSimpleSerializer, NoteLikeSerializer,
    NoteFavoriteSerializer, UserSerializer, DraftNoteSerializer
)
from django.db.models import Prefetch
from .utils import UnixTimestamp
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Count, F, ExpressionWrapper, IntegerField, FloatField, Case, When, Value, Q
from .permissions import IsOwnerOrReadOnly
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly, IsAdminUser
from io import BytesIO
from .ai_conclude import SparkLiteClient


User = get_user_model()

# 笔记列表（测试用），已验证
class NoteListView(APIView):
    serializer_class = NoteSerializer
    permission_classes = [AllowAny]
    def get(self, request):
        # 获取所有笔记
        notes = Note.objects.all()
        serializer = NoteSerializer(notes, many=True, context={'request': request})
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


def move_file(src_path, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, os.path.basename(src_path))
    shutil.move(src_path, dest_path)
    return dest_path

# 草稿笔记
class DraftNoteViewSet(viewsets.ModelViewSet):
    queryset = DraftNote.objects.all()
    serializer_class = DraftNoteSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_queryset()
        return super().get_queryset().filter(author=self.request.user)

    def create(self, request, *args, **kwargs):
        # 1. 验证并保存草稿
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        draft = serializer.save(author=request.user)

        # 2. 处理所有附件（图片／视频／封面／文件）
        self.handle_attachments(draft, request.FILES)

        # 3. 重新序列化，返回完整对象
        out_serializer = self.get_serializer(draft, context={'request': request})
        headers = self.get_success_headers(out_serializer.data)
        return Response({
            "code": status.HTTP_201_CREATED,
            "message": "Draft created successfully",
            "data": out_serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    def handle_attachments(self, draft, files):
        # 1. 手动上传封面
        if 'cover_image' in files:
            ci = files['cover_image']
            draft.cover_image.save(ci.name, ci, save=False)
            draft.uploaded_cover_type = 'uploaded'
            draft.uploaded_cover_path = draft.cover_image.name
            draft.save()
            return

        # 2. 图片集合
        if files.getlist('note_images'):
            images = files.getlist('note_images')
            NoteImage.objects.filter(draft_note=draft).delete()

            for f in images:
                # 调用 compress_image 压缩
                try:
                    compressed = compress_image(f)
                except ValueError as e:
                    raise ValidationError(f"图片处理失败：{e}")
                NoteImage.objects.create(draft_note=draft, image=compressed)

            # 取第一张压缩后的图作为封面预览
            first = draft.draft_images.first().image
            draft.uploaded_cover_type = 'image'
            draft.uploaded_cover_path = first.name
            draft.save()
        # 3. 视频封面
        if 'note_video' in files:
            vid = files['note_video']
            draft.note_video.save(vid.name, vid, save=False)
            draft.save()

            # 1) 生成临时文件路径，不保持打开句柄
            tmp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp_path = tmp_file.name
            tmp_file.close()

            # 2) FFmpeg 抽帧到临时路径
            cmd = [
                settings.FFMPEG_PATH,
                '-i', draft.note_video.path,
                '-ss', '00:00:01',
                '-frames:v', '1',
                '-update', '1',
                '-y', tmp_path
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # 3) 构建目标路径，基于 draft.id 创建子文件夹
                dest_rel = f'draft_covers/{draft.id}/{uuid.uuid4().hex}.jpg'
                full_dest = os.path.join(settings.MEDIA_ROOT, dest_rel)
                os.makedirs(os.path.dirname(full_dest), exist_ok=True)

                # 4) 使用 shutil.move（支持跨盘符）
                shutil.move(tmp_path, full_dest)

                # 5) 更新 DraftNote 实例
                draft.uploaded_cover_type = 'video'
                draft.uploaded_cover_path = dest_rel
                draft.save()
            except Exception as e:
                # 6) 如果失败，尝试清理临时文件
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise ValidationError(f"视频封面提取失败: {e}")

        # 5. 草稿笔记文件（最多3个）
        draft.draft_files.all().delete()
        for f in files.getlist('note_files'):
            NoteFile.objects.create(draft_note=draft, file=f)

        # 4. 文本生成候选封面
        covers = generate_cover_images(
            extract_keywords({
                'title': draft.title,
                'content': draft.content,
                'body': draft.body,
                'category': draft.category
            }),
            draft.id
        )
        draft.generated_covers = covers
        draft.save()

    @action(detail=True, methods=['post'])
    def regenerate_covers(self, request, pk=None):
        draft = self.get_object()
        if draft.author != request.user:
            raise PermissionDenied()
        # 清理旧图
        for p in draft.generated_covers:
            f = os.path.join(settings.MEDIA_ROOT, p)
            if os.path.exists(f):
                os.remove(f)
        self.handle_attachments(draft, {})
        return Response(DraftNoteSerializer(draft, context={'request': request}).data)

    @action(detail=True, methods=['patch'])
    def select_cover(self, request, pk=None):
        draft = self.get_object()
        if draft.author != request.user:
            raise PermissionDenied()
        t = request.data.get('type')
        url = request.data.get('url')

        if t == 'uploaded':
            draft.cover_image.name = draft.uploaded_cover_path
        elif t == 'generated':
            key = url.split(settings.MEDIA_URL)[-1]
            if key not in draft.generated_covers:
                raise ValidationError('无效封面')
            draft.cover_image.name = key
        else:
            raise ValidationError('无效类型')

        draft.save()
        return Response({'msg': '封面更新成功'})


class PublishedNoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer

    @action(detail=False, methods=['post'])
    def publish(self, request):
        draft_id = request.data.get('draft_id')
        try:
            draft_id = int(draft_id)
        except (TypeError, ValueError):
            raise ValidationError({'draft_id': '草稿 ID 无效'})

        draft = request.user.draft_notes.filter(id=draft_id).first()
        if not draft:
            raise ValidationError({'draft_id': '无效草稿'})
        if not draft.cover_image:
            raise ValidationError({'cover_image': '必须选择封面'})

        with transaction.atomic():
            # 创建正式笔记
            note = Note.objects.create(
                title=draft.title,
                content=draft.content,
                category=draft.category,
                body=draft.body,
                author=draft.author,
            )

            # 搬迁草稿图片到正式笔记
            for img in draft.draft_images.all():
                new_path = move_file(
                    img.image.path,
                    os.path.join(settings.MEDIA_ROOT, 'note_images', str(note.id))
                )
                NoteImage.objects.create(
                    published_note=note,
                    image=f'note_images/{note.id}/{os.path.basename(new_path)}'
                )

            # 搬迁视频
            if draft.note_video:
                new_path = move_file(
                    draft.note_video.path,
                    os.path.join(settings.MEDIA_ROOT, 'note_videos', str(note.id))
                )
                note.note_video.name = f'note_videos/{note.id}/{os.path.basename(new_path)}'

            # 搬迁封面
            if draft.cover_image:
                new_path = move_file(
                    draft.cover_image.path,
                    os.path.join(settings.MEDIA_ROOT, 'note_covers', str(note.id))
                )
                note.cover_image.name = f'note_covers/{note.id}/{os.path.basename(new_path)}'

            # 搬迁草稿中的文件附件
            for file in draft.draft_files.all():
                new_path = move_file(
                    file.file.path,
                    os.path.join(settings.MEDIA_ROOT, 'note_files', str(note.id))
                )
                nf = NoteFile.objects.create(
                    published_note=note,
                    file=f'note_files/{note.id}/{os.path.basename(new_path)}'
                )
            # 更新用户笔记总数
            User.objects.filter(pk=note.author_id).update(total_notes=F('total_notes') + 1)
            user = User.objects.select_for_update().get(pk=request.user.pk)

            # 积分逻辑
            is_first = (user.total_notes == 1)
            add_points = 0
            source = None

            if is_first and not user.first_publish_bonus_given:
                add_points = 50
                source = 'first_publish'
                user.first_publish_bonus_given = True
            else:
                # 日常发布，每日最多 30 分，每篇最多 10 分
                if user.points_note_publish < 30:
                    add_points = min(10, 30 - user.points_note_publish)
                    source = 'daily_publish'
                    user.points_note_publish += add_points

            if add_points > 0:
                user.points = F('points') + add_points
                PointHistory.objects.create(
                    user=user,
                    amount=add_points,
                    source=source,
                    description=f"{'首发奖励' if source == 'first_publish' else '发布笔记'} 获得 {add_points} 分"
                )

            note.save()
            user.save(update_fields=['points', 'points_note_publish', 'first_publish_bonus_given'])
            # 验证序列化
            serialized = NoteSerializer(note, context={'request': request}).data
            # 删除草稿
            draft.delete()
        return Response(serialized, status=status.HTTP_201_CREATED)


# 封面缩略图生成
class CoverThumbnailView(APIView):
    def get(self, request, note_id, filename):
        note = get_object_or_404(Note, pk=note_id)
        original_path = next((p for p in note.generated_covers if filename in p), None)

        if not original_path:
            return HttpResponse(status=404)

        full_path = os.path.join(settings.MEDIA_ROOT, original_path)

        try:
            with Image.open(full_path) as img:
                img.thumbnail((300, 200))
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return HttpResponse(buffer.getvalue(), content_type="image/jpeg")
        except Exception as e:
            return HttpResponse(str(e), status=500)


# 定义了一些预览上传的笔记文件的方法，已验证 （PDF文件有的可以预览内容有的不行）
# def preview_note(request, note_id):
#     note = get_object_or_404(Note, id=note_id)
#     file_path = note.file.path if note.file else None
#
#     if not file_path:
#         return HttpResponse("No file attached to this note.")
#
#     file_extension = os.path.splitext(file_path)[1].lower()
#
#     if file_extension == '.pdf':
#         # 使用 PyMuPDF 将 PDF 转换为 HTML
#         with fitz.open(file_path) as doc:
#             html_content = ""
#             for page in doc:
#                 html_content += page.get_text("html")
#             return HttpResponse(html_content)
#
#     elif file_extension in ['.doc', '.docx']:
#         # 使用 python-docx 将 Word 转换为 HTML
#         document = docx.Document(file_path)
#         html_content = ""
#         for paragraph in document.paragraphs:
#             html_content += f"<p>{paragraph.text}</p>"
#         return HttpResponse(html_content)
#
#     elif file_extension == '.md':
#         # 使用 markdown 库将 Markdown 转换为 HTML
#         with open(file_path, 'r') as f:
#             markdown_content = f.read()
#             html_content = markdown.markdown(markdown_content)
#             return HttpResponse(html_content)
#     else:
#         raise Http404("Unsupported file type.")


# 异步功能根据热度排出的Top 10，已验证并推荐使用
class TopNotesView(generics.ListAPIView):
    serializer_class = NoteSimpleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # 从TopNote模型中获取Top 10笔记
        top_notes = TopNote.objects.order_by('rank').select_related('note')[:10]
        # 提取关联的 Note 对象列表
        return [tn.note for tn in top_notes]


# 按类别进行热度排序并加上了分页处理，已验证
class NotesByCategoryView(generics.ListAPIView):
    serializer_class = NoteSimpleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        category = self.kwargs['category']
        page_number = self.kwargs.get('page_number', 1)
        page_size = self.kwargs.get('page_size', 10)

        # 从TopNote模型中获取指定类别的笔记
        top_notes = TopNote.objects.filter(note__category=category).order_by('rank')

        # 使用 Paginator 进行分页
        paginator = Paginator(top_notes, page_size)
        page = paginator.get_page(page_number)

        # 返回当前页的笔记对象列表
        return [top_note.note for top_note in page.object_list]


# 根据热度排出的Top 10，没有采用上面提到的异步处理方案，在每次发送请求时现排，已验证
# class Top10NotesView(generics.ListAPIView):
#     serializer_class = NoteSerializer
#     permission_classes = [IsAuthenticatedOrReadOnly]
#
#     def get_queryset(self):
#         # 过滤出所有用户的非私有笔记
#         queryset = Note.objects.filter(is_private=False)
#
#         # 定义一个最小堆，用于存储 Top 10 笔记
#         top_10_notes = []
#
#         for note in queryset:
#             # 计算热度
#             popularity = 0.6 * note.views_count + 0.3 * note.likes_count + 0.1 * note.comments_count
#
#             # 如果堆未满或当前笔记的热度大于堆中的最小值
#             if len(top_10_notes) < 10 or popularity > top_10_notes[0][0]:
#                 if len(top_10_notes) == 10:
#                     # 如果堆已满，移除堆顶元素（最小值）
#                     heapq.heappop(top_10_notes)
#                 # 将当前笔记加入堆中
#                 heapq.heappush(top_10_notes, (popularity, note.id, note))
#
#         # 从堆中提取 Top 10 笔记，并按热度降序排序
#         top_10_notes = [note for _, _, note in heapq.nlargest(10, top_10_notes)]
#
#         return top_10_notes


# 列出某个用户的所有公开笔记（或者用户本人的所有笔记），并按是否置顶和创建时间进行排序，已验证
class UserNotesView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        current_user = self.request.user
        queryset = Note.objects.filter(author_id=user_id)

        # 如果是所有者本人请求，返回所有笔记
        if current_user.is_authenticated and current_user.id == user_id:
            return queryset.order_by('-is_pinned', '-created_at')
        # 否则仅返回公开笔记
        return queryset.filter(is_private=False).order_by('-is_pinned', '-created_at')


# 用户访问、修改、删除笔记，已验证非笔记所有者用户访问时浏览数增加，剩下的修改和删除未验证
class NoteRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # 允许访问：自己的所有笔记 + 其他用户的公开笔记
            return Note.objects.filter(
                Q(author=user) | Q(is_private=False)
            )
        else:
            # 未登录用户只能访问公开笔记
            return Note.objects.filter(is_private=False)

    #retrieve方法处理 GET 请求，如果请求用户不是笔记的作者，则增加笔记的浏览数，并返回笔记信息
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # 如果请求用户不是笔记的作者，则增加浏览数
        if request.user != instance.author:
            instance.views_count += 1
            instance.save()
            # 同时更新作者的总浏览量
            instance.author.total_views += 1
            instance.author.save()
        serializer = self.get_serializer(instance, context={'request': request})

        return Response({
            "code": status.HTTP_200_OK,
            "message": "Note retrieved successfully",
            "data": serializer.data,
        }, status=status.HTTP_200_OK)

    #update方法处理 PUT 和 PATCH 请求，更新笔记内容，并返回成功消息和更新后的数据
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "code": status.HTTP_200_OK,
            "message": "Note updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    #destroy方法处理DELETE请求，删除笔记，并返回成功消息
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        author_id = instance.author_id
        with transaction.atomic():  # 添加事务保障原子性
            # 减少用户笔记总数
            User.objects.filter(pk=author_id).update(total_notes=F('total_notes') - 1)
            instance.delete()
        return Response({
            "code": status.HTTP_204_NO_CONTENT,
            "message": "Note deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)


# 点赞视图，已验证
class NoteLikeView(generics.GenericAPIView):
    queryset = Note.objects.all()
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        note = self.get_object()
        user = request.user

        # 检查是否已点赞
        if not Like.objects.filter(note=note, user=user).exists():
            Like.objects.create(note=note, user=user)  # 通过中间模型创建关联
            return Response({'detail': 'Liked'}, status=status.HTTP_201_CREATED)
        return Response({'detail': 'Already liked'}, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        note = self.get_object()
        user = request.user

        # 精确删除当前用户的点赞记录
        deleted, _ = Like.objects.filter(note=note, user=user).delete()
        if deleted > 0:
            return Response({'detail': 'Unliked'}, status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Not liked'}, status=status.HTTP_200_OK)


# 获取用户点赞过的笔记
class UserLikedNotesView(generics.ListAPIView):
    serializer_class = NoteLikeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 获取当前用户点赞的所有笔记（通过反向关联）
        return (
            self.request.user.liked_notes
            .select_related('author')  # 预加载作者信息
            .prefetch_related('likes')  # 预加载点赞关系
            .annotate_liked_time(self.request.user)
        )

    def get_serializer_context(self):
        # 传递request对象用于构建完整URL
        return {'request': self.request}


# 收藏试图
class NoteFavoriteView(generics.GenericAPIView):
    queryset = Note.objects.all()
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        note = self.get_object()
        user = request.user

        # 检查是否已收藏
        if not Favorite.objects.filter(note=note, user=user).exists():
            Favorite.objects.create(note=note, user=user)
            return Response({'detail': 'Favorited'}, status=status.HTTP_201_CREATED)
        return Response({'detail': 'Already favorited'}, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        note = self.get_object()
        user = request.user

        # 精确删除当前用户的收藏记录
        deleted, _ = Favorite.objects.filter(note=note, user=user).delete()
        if deleted > 0:
            return Response({'detail': 'Unfavorited'}, status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Not favorited'}, status=status.HTTP_200_OK)


# 收藏笔记列表
class UserFavoriteNotesView(generics.ListAPIView):
    serializer_class = NoteFavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 通过 Favorite 模型反向关联获取当前用户收藏的 Note 实例
        return Note.objects.filter(favorited_by__user=self.request.user)\
            .select_related('author')\
            .prefetch_related('favorited_by')

    def get_serializer_context(self):
        # 传递 request 对象以构建完整 URL（如果序列化器中需要使用）
        return {'request': self.request}


# 获取根评论
class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RootCommentPagination

    def get_queryset(self):
        note_id = self.kwargs['note_id']
        qs = Comment.objects.filter(note_id=note_id, parent__isnull=True)

        # 使用 MySQL 兼容的时间戳注解
        qs = qs.annotate(
            annotated_likes=Count('likes'),
            created_ts=UnixTimestamp(F('created_at'))  # 关键修改
        ).annotate(
            sort_group=Case(
                When(is_refreshed=False, then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            ),
            ordering_key=Case(
                When(is_refreshed=False,
                     then=ExpressionWrapper(-F('created_ts'), output_field=FloatField())),
                default=ExpressionWrapper(-F('annotated_likes'), output_field=FloatField())
            )
        ).order_by('sort_group', 'ordering_key', '-id')

        # 子评论查询集同样使用 UnixTimestamp
        replies_qs = Comment.objects.filter(parent__isnull=False).annotate(
            annotated_likes=Count('likes'),
            created_ts=UnixTimestamp(F('created_at'))  # 关键修改
        ).annotate(
            sort_group=Case(
                When(is_refreshed=False, then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            ),
            ordering_key=Case(
                When(is_refreshed=False,
                     then=ExpressionWrapper(-F('created_ts'), output_field=FloatField())),
                default=ExpressionWrapper(-F('annotated_likes'), output_field=FloatField())
            )
        ).order_by('sort_group', 'ordering_key', '-id')

        qs = qs.prefetch_related(
            Prefetch('replies', queryset=replies_qs[:5], to_attr='filtered_replies')
        )
        return qs

    def perform_create(self, serializer):
        note = get_object_or_404(Note, id=self.kwargs['note_id'])
        serializer.save(note=note, user=self.request.user)


# 获取根评论下的所有子评论
class SubCommentListView(generics.ListAPIView):
    serializer_class = CommentSerializer
    pagination_class = SubCommentPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        root_id = self.kwargs['root_id']
        try:
            root_comment = Comment.objects.get(id=root_id)
        except Comment.DoesNotExist:
            return Comment.objects.none()

        # 获取所有后代评论（建议改用 CTE 优化）
        all_descendants = root_comment.get_all_descendants()
        comment_ids = [c.id for c in all_descendants]

        qs = Comment.objects.filter(id__in=comment_ids)
        qs = qs.annotate(
            annotated_likes=Count('likes'),
            created_ts=UnixTimestamp(F('created_at'))  # 关键修改
        ).annotate(
            sort_group=Case(
                When(is_refreshed=False, then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            ),
            ordering_key=Case(
                When(is_refreshed=False,
                     then=ExpressionWrapper(-F('created_ts'), output_field=FloatField())),
                default=ExpressionWrapper(-F('annotated_likes'), output_field=FloatField())
            )
        ).select_related('user').order_by('sort_group', 'ordering_key', '-id')
        return qs


# 删除评论（改为物理删除）
class CommentDestroyView(generics.DestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def perform_destroy(self, instance):
        # 可以直接调用delete()方法，Django会自动级联删除所有子评论
        instance.delete()


# 评论点赞
class CommentLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        user = request.user

        # 互斥逻辑：如果用户之前点过不喜欢，先取消不喜欢
        if comment.dislikes.filter(id=user.id).exists():
            comment.dislikes.remove(user)

        # 处理点赞/取消点赞
        if comment.likes.filter(id=user.id).exists():
            comment.likes.remove(user)
            liked = False
        else:
            comment.likes.add(user)
            liked = True

        return Response({
            'like_count': comment.likes.count(),
            'is_liked': liked,
            'dislike_count': comment.dislikes.count(),
            'is_disliked': False
        }, status=status.HTTP_200_OK)


# 不喜欢的评论
class CommentDislikeView(APIView):
    """处理不喜欢/取消不喜欢操作"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        user = request.user

        # 自动取消点赞（互斥逻辑）
        if comment.likes.filter(id=user.id).exists():
            comment.likes.remove(user)

        # 处理不喜欢状态
        if comment.dislikes.filter(id=user.id).exists():
            comment.dislikes.remove(user)
            disliked = False
        else:
            comment.dislikes.add(user)
            disliked = True

        return Response({
            'dislike_count': comment.dislike_count,
            'is_disliked': disliked,
            'like_count': comment.like_count,
            'is_liked': False  # 确保取消点赞状态
        }, status=status.HTTP_200_OK)


# 搜索视图
class NoteSearchView(generics.ListAPIView):
    serializer_class = NoteSimpleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    page_size = 10

    def get_queryset(self):
        # 获取查询参数
        title = self.request.query_params.get('title', '')
        content = self.request.query_params.get('content', '')
        category = self.request.query_params.get('category', '')
        author = self.request.query_params.get('author', '')
        body = self.request.query_params.get('body', '')

        # 进行模糊查询
        queryset = Note.objects.filter(
            title__icontains=title,
            content__icontains=content,
            category__icontains=category,
            author__username__icontains=author,
            body__icontains=body,
        )

        # 从 TopNote 模型中获取指定条件的笔记，并按 rank 排序
        top_notes = TopNote.objects.filter(note__in=queryset).order_by('rank')
        # 返回当前页的笔记对象列表
        return [top_note.note for top_note in top_notes]


# 关注功能,URL中传入要关注的用户ID（pk）
class FollowToggleView(generics.GenericAPIView):

    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        target_user = self.get_object()  # 获取目标用户
        current_user = request.user

        # 防止用户关注自己
        if target_user == current_user:
            return Response({'detail': '不能关注自己'}, status=status.HTTP_400_BAD_REQUEST)

        # 如果已经关注，则取消关注；否则关注
        if target_user in current_user.following.all():
            current_user.following.remove(target_user)
            # 同时删除对应的关注通知
            Notification.objects.filter(
                recipient=target_user,
                sender=current_user,
                notification_type='follow'
            ).delete()
            return Response({'detail': '已取消关注'}, status=status.HTTP_204_NO_CONTENT)
        else:
            current_user.following.add(target_user)
            return Response({'detail': '关注成功'}, status=status.HTTP_201_CREATED)


# 关注列表
class FollowedUsersListView(generics.ListAPIView):
    """
    列出当前登录用户关注的所有用户（已关注列表）
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.following.all()


# 粉丝列表
class FollowersListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 获取当前登录用户的所有粉丝
        return self.request.user.followers.all()


# AI笔记总结
class NoteSummarizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        note_id = request.data.get('note_id')
        if not note_id:
            return Response({'error': '需要提供 note_id'}, status=status.HTTP_400_BAD_REQUEST)

        note = get_object_or_404(Note, pk=note_id, author=request.user)

        # 使用事务和 select_for_update 锁定用户记录
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if user.ai_limits <= 0:
                return Response({'error': 'AI 使用次数已用尽'}, status=status.HTTP_403_FORBIDDEN)

            prompt = f"请为以下笔记内容生成简要总结：\n\n{note.content}"
            try:
                summary = SparkLiteClient.summarize(prompt)
            except requests.exceptions.RequestException as e:
                return Response({'error': f'调用 AI 接口失败：{str(e)}'},
                                status=status.HTTP_502_BAD_GATEWAY)
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                return Response({'error': f'AI 返回数据异常：{str(e)}'},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 扣减 AI 使用次数并记录历史
            user.ai_limits -= 1
            user.save(update_fields=['ai_limits'])

        # 事务结束后返回结果
        return Response({
            'success': True,
            'summary': summary,
            'ai_limits': user.ai_limits
        }, status=status.HTTP_200_OK)
