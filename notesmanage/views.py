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
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
import fitz  # PyMuPDF
import docx
import markdown


class NoteListView(APIView):
    serializer_class = NoteSerializer
    permission_classes = [AllowAny]
    def get(self, request):
        # 获取所有笔记
        notes = Note.objects.all()
        serializer = NoteSerializer(notes, many=True)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


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

def create_note(request):
    if request.method == 'POST':
        form = CommentForm(data=request.POST)
        if form.is_valid():
            form.save()
            return render(request, 'form-post-finished.html')
    form = CommentForm()
    return render(request, 'create_note.html', {'form': form})


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


#根据热度排出的Top 10
class TopNotesView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # 直接从TopNote模型中获取热门笔记
        return TopNote.objects.all().values_list('note', flat=True)

# class MultipleUsersNotesView(generics.ListAPIView):
#     serializer_class = NoteSerializer
#     permission_classes = [permissions.IsAuthenticatedOrReadOnly]
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
#                 heapq.heappush(top_10_notes, (popularity, note))
#
#         # 从堆中提取 Top 10 笔记，并按热度降序排序
#         top_10_notes = [note for _, note in heapq.nlargest(10, top_10_notes)]
#
#         return top_10_notes

#列出某个用户的所有公开笔记，并按是否置顶和创建时间进行排序
class UserNotesView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        return Note.objects.filter(author_id=user_id, is_private=False).order_by('-is_pinned', '-created_at')


class NoteRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

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



class NoteLikeView(generics.GenericAPIView):
    queryset = Note.objects.all()
    permission_classes = [permissions.IsAuthenticated]

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


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        note_id = self.kwargs['note_id']
        return Comment.objects.filter(note_id=note_id)

    def perform_create(self, serializer):
        note_id = self.kwargs['note_id']
        serializer.save(author=self.request.user, note_id=note_id)


class PinNoteView(generics.UpdateAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        note = self.get_object()
        if note.author == request.user:
            note.is_pinned = not note.is_pinned
            note.save()
            return Response({'detail': 'Pinned' if note.is_pinned else 'Unpinned'}, status=status.HTTP_200_OK)
        return Response({'detail': 'You are not the author of this note'}, status=status.HTTP_403_FORBIDDEN)


class NoteSearchView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if query:
            return Note.objects.filter(
                (Q(title__icontains=query) | Q(content__icontains=query) | Q(category__icontains=query)) & Q(
                    is_private=False)
            ).order_by('-created_at')
        return Note.objects.filter(is_private=False).order_by('-created_at')

class NoteDetailView(RetrieveAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    lookup_field = 'id'
