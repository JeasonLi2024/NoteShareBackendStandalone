import os
from rest_framework import generics, permissions, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from .models import Note, Comment, Like
from .serializers import NoteSerializer, CommentSerializer
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
import fitz  # PyMuPDF
import docx
import markdown

class NoteListCreateView(generics.ListCreateAPIView):
    queryset = Note.objects.filter(is_private=False)
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

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

class MultipleUsersNotesView(generics.ListAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # 获取查询参数中的用户 ID 列表
        user_ids = self.request.query_params.get('user_ids', '').split(',')
        # 过滤出这些用户的非私有笔记
        return Note.objects.filter(author_id__in=user_ids, is_private=False).order_by('-is_pinned', '-created_at')


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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.views_count += 1
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


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
