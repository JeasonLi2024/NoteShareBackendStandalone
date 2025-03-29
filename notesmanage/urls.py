from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views
from notesmanage.views import (
    UserNotesView, NoteCreateView, NoteRetrieveUpdateDestroyView,
    NoteLikeView, CommentListCreateView, PinNoteView, NoteSearchView,
    TopNotesView, preview_note, NoteDetailView, NoteListView, Top10NotesView
)

urlpatterns = [
                  #通过表单实现的笔记上传页面
                  path('create/', views.create_note, name='create_note'),
                  #无保护的笔记信息列表（测试用）
                  path('notes_list/', NoteListView.as_view(), name='note-list'),
                  #访问某一用户的所有公开笔记
                  path('users/<int:user_id>/notes/', UserNotesView.as_view(), name='user-notes'),
                  #使用视图逻辑的用户创建笔记
                  path('notes/create', NoteCreateView.as_view(), name='note-list-create'),
                  #多功能，集笔记访问（客人用户访问时read_only，同时浏览数增加；笔记所有者访问时可以对笔记进行修改和删除）
                  path('notes/<int:pk>/', NoteRetrieveUpdateDestroyView.as_view(), name='note-retrieve-update-destroy'),
                  #点赞功能
                  path('notes/<int:pk>/like/', NoteLikeView.as_view(), name='note-like'),
                  #评论功能
                  path('notes/<int:note_id>/comments/', CommentListCreateView.as_view(), name='comment-list-create'),
                  #笔记置顶功能（这个路由似乎没什么用）
                  path('notes/<int:pk>/pin/', PinNoteView.as_view(), name='note-pin'),
                  #笔记搜索
                  path('notes/search/', NoteSearchView.as_view(), name='note-search'),
                  #笔记首页展示热门笔记Top10
                  path('notes/Top/', TopNotesView.as_view(), name='top-notes'),
                  path('notes/Top_10/', Top10NotesView.as_view(), name='top10-notes'),
                  #笔记预览（似乎也不需用设置这个路由）
                  path('notes/<int:note_id>/preview/', preview_note, name='note-preview'),
                  #笔记详细信息（面向用户）
                  path('notes/<int:note_id>/detail/', NoteDetailView.as_view(), name='note-detail'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)