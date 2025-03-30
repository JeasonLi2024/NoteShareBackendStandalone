import os
import heapq
from rest_framework import generics, permissions, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Note, Comment, Like, TopNote
from .serializers import NoteSerializer, CommentSerializer
from django.db.models import Q
from django.http import HttpResponse, Http404
from .forms import CommentForm
from django.shortcuts import get_object_or_404, render, redirect
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny, IsAuthenticatedOrReadOnly
import fitz  # PyMuPDF
import docx
import markdown

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

# 新建笔记，没有在后端可视化验证，可能需要在前端验证，前端可能需要配置CKEDITOR_5
class NoteCreateView(generics.ListCreateAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    # permission_classes = [IsAuthenticated]
    permission_classes = [AllowAny]
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "code": status.HTTP_201_CREATED,
            "message": "Note created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

# 使用表单经过验证，但网页十分简洁，详见templates目录下的create_note.html（该目录下的另一个文件夹中的.html暂时没有使用）
def create_note(request):
    if request.method == 'POST':
        form = CommentForm(data=request.POST)
        if form.is_valid():
            form.save()
            return render(request, 'form-post-finished.html') # 这个地方的逻辑时提交成功后跳转到一个名为form-post-finished.html的页面，我没有在后端设置，这个相关路由只是为了在后端可视化测试CKEDITOR_5是否可用
    form = CommentForm()
    return render(request, 'create_note.html', {'form': form})

# 定义了一些预览上传的笔记文件的方法，已验证 （PDF文件有的可以预览内容有的不行）
def preview_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    file_path = note.file.path if note.file else None

    if not file_path:
        return HttpResponse("No file attached to this note.")

    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == '.pdf':
        # 使用 PyMuPDF 将 PDF 转换为 HTML
        with fitz.open(file_path) as doc:
            html_content = ""
            for page in doc:
                html_content += page.get_text("html")
            return HttpResponse(html_content)

    elif file_extension in ['.doc', '.docx']:
        # 使用 python-docx 将 Word 转换为 HTML
        document = docx.Document(file_path)
        html_content = ""
        for paragraph in document.paragraphs:
            html_content += f"<p>{paragraph.text}</p>"
        return HttpResponse(html_content)

    elif file_extension == '.md':
        # 使用 markdown 库将 Markdown 转换为 HTML
        with open(file_path, 'r') as f:
            markdown_content = f.read()
            html_content = markdown.markdown(markdown_content)
            return HttpResponse(html_content)
    else:
        raise Http404("Unsupported file type.")


# 异步功能根据热度排出的Top 10，未测试
# class TopNotesView(generics.ListAPIView):
#     serializer_class = NoteSerializer
#     permission_classes = [permissions.IsAuthenticatedOrReadOnly]
#
#     def get_queryset(self):
#         # 直接从TopNote模型中获取热门笔记
#         return TopNote.objects.all().values_list('note', flat=True)

class TopNotesView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # 直接通过索引快速定位 Top 10
        return Note.objects.filter(is_private=False).order_by('-popularity')[:10]

# 根据热度排出的Top 10，没有采用上面提到的异步处理方案，在每次发送请求时现排，已验证
class Top10NotesView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # 过滤出所有用户的非私有笔记
        queryset = Note.objects.filter(is_private=False)

        # 定义一个最小堆，用于存储 Top 10 笔记
        top_10_notes = []

        for note in queryset:
            # 计算热度
            popularity = 0.6 * note.views_count + 0.3 * note.likes_count + 0.1 * note.comments_count

            # 如果堆未满或当前笔记的热度大于堆中的最小值
            if len(top_10_notes) < 10 or popularity > top_10_notes[0][0]:
                if len(top_10_notes) == 10:
                    # 如果堆已满，移除堆顶元素（最小值）
                    heapq.heappop(top_10_notes)
                # 将当前笔记加入堆中
                heapq.heappush(top_10_notes, (popularity, note.id, note))

        # 从堆中提取 Top 10 笔记，并按热度降序排序
        top_10_notes = [note for _, _, note in heapq.nlargest(10, top_10_notes)]

        return top_10_notes


# 列出某个用户的所有公开笔记，并按是否置顶和创建时间进行排序，未完全验证（需要在更多测试数据下进行）
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
        if self.request.user.is_authenticated:
            return Note.objects.filter(author=self.request.user)
        return Note.objects.filter(is_private=False)

    #retrieve方法处理 GET 请求，如果请求用户不是笔记的作者，则增加笔记的浏览数，并返回笔记信息
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # 如果请求用户不是笔记的作者，则增加浏览数
        if request.user != instance.author:
            instance.views_count += 1
            instance.save()
        serializer = self.get_serializer(instance)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "Note retrieved successfully",
            "data": serializer.data
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
        instance.delete()
        return Response({
            "code": status.HTTP_204_NO_CONTENT,
            "message": "Note deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)


# 点赞视图，未验证
class NoteLikeView(generics.GenericAPIView):
    queryset = Note.objects.all()
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        note = self.get_object()
        if not note.likes.filter(id=request.user.id).exists():
            Like.objects.create(user=request.user, note=note)
            return Response({'detail': 'Liked'}, status=status.HTTP_201_CREATED)
        return Response({'detail': 'Already liked'}, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        note = self.get_object()
        like = Like.objects.filter(user=request.user, note=note).first()
        if like:
            like.delete()
            return Response({'detail': 'Unliked'}, status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Not liked'}, status=status.HTTP_200_OK)

# 评论视图，未验证
class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        note_id = self.kwargs['note_id']
        return Comment.objects.filter(note_id=note_id)

    def perform_create(self, serializer):
        note_id = self.kwargs['note_id']
        serializer.save(author=self.request.user, note_id=note_id)

# 置顶视图，感觉不需要单独设计此功能的视图，在模型中已添加该类型字段
class PinNoteView(generics.UpdateAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        note = self.get_object()
        if note.author == request.user:
            note.is_pinned = not note.is_pinned
            note.save()
            return Response({'detail': 'Pinned' if note.is_pinned else 'Unpinned'}, status=status.HTTP_200_OK)
        return Response({'detail': 'You are not the author of this note'}, status=status.HTTP_403_FORBIDDEN)

# 搜索视图，未验证
class NoteSearchView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if query:
            return Note.objects.filter(
                (Q(title__icontains=query) | Q(content__icontains=query) | Q(category__icontains=query)) & Q(
                    is_private=False)
            ).order_by('-created_at')
        return Note.objects.filter(is_private=False).order_by('-created_at')

# 笔记详情视图，是否需要有待验证，原先的想法是利用此功能实现用户访问其他人的笔记时可以看到对方笔记的详细内容，但AI给的这个代码实现了类似管理员的视角，显然有点问题哈哈
class NoteDetailView(RetrieveAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    lookup_field = 'id'
