from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from notesmanage.views import (
    UserNotesView, NoteCreateView, NoteRetrieveUpdateDestroyView,
    NoteLikeView, CommentListCreateView, PinNoteView, NoteSearchView,
    MultipleUsersNotesView, preview_note, NoteDetailView, NoteListView
)

urlpatterns = [
                  path('notes_list/', NoteListView.as_view(), name='note-list'),
                  path('users/<int:user_id>/notes/', UserNotesView.as_view(), name='user-notes'),
                  path('notes/create', NoteCreateView.as_view(), name='note-list-create'),
                  path('notes/<int:pk>/', NoteRetrieveUpdateDestroyView.as_view(), name='note-retrieve-update-destroy'),
                  path('notes/<int:pk>/like/', NoteLikeView.as_view(), name='note-like'),
                  path('notes/<int:note_id>/comments/', CommentListCreateView.as_view(), name='comment-list-create'),
                  path('notes/<int:pk>/pin/', PinNoteView.as_view(), name='note-pin'),
                  path('notes/search/', NoteSearchView.as_view(), name='note-search'),
                  path('users/notes/multiple/', MultipleUsersNotesView.as_view(), name='multiple-users-notes'),
                  path('notes/<int:note_id>/preview/', preview_note, name='note-preview'),
                  path('notes/<int:note_id>/detail/', NoteDetailView.as_view(), name='note-detail'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)