from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from notesmanage.views import (
    UserNotesView, NoteCreateView, NoteRetrieveUpdateDestroyView,
    NoteLikeView,  NoteSearchView, CommentDestroyView, CommentLikeView,
    TopNotesView, preview_note, NoteListView, NotesByCategoryView,
    UserLikedNotesView, CommentListCreateView, CommentDislikeView, SubCommentListView,
    UserFavoriteNotesView, NoteFavoriteView, FollowToggleView, FollowedUsersListView
)
from .ai_conclude import spark_lite

urlpatterns = [
                  # 通过表单实现的笔记上传页面
                  # path('create/', views.create_note, name='create_note'),
                  # 无保护的笔记信息列表（测试用）
                  path('notes_list/', NoteListView.as_view(), name='note-list'),
                  # 访问某一用户的所有（公开）笔记
                  path('user/<int:user_id>/notes/', UserNotesView.as_view(), name='user-notes'),
                  # 使用视图逻辑的用户创建笔记
                  path('notes/create', NoteCreateView.as_view(), name='note-list-create'),
                  # 多功能，集笔记访问（客人用户访问时read_only，同时浏览数增加；笔记所有者访问时可以对笔记进行修改和删除）
                  path('notes/<int:pk>/', NoteRetrieveUpdateDestroyView.as_view(), name='note-retrieve-update-destroy'),
                  # 关注功能
                  path('follow/<int:pk>/', FollowToggleView.as_view(), name='follow-toggle'),
                  # 关注列表
                  path('following/', FollowedUsersListView.as_view(), name='followed-users'),
                  # 点赞功能
                  path('notes/<int:pk>/like/', NoteLikeView.as_view(), name='note-like'),
                  # 用户点过赞的笔记
                  path('user/me/liked-notes/', UserLikedNotesView.as_view(), name='user-liked-notes'),
                  # 收藏功能
                  path('notes/<int:pk>/favorite/', NoteFavoriteView.as_view(), name='note-favorite'),
                  # 用户收藏的笔记
                  path('user/me/favorited-notes/', UserFavoriteNotesView.as_view(), name='user-favorited-notes'),
                  # 笔记评论接口
                  path('notes/<int:note_id>/comments/', CommentListCreateView.as_view(), name='note-comments'),
                  # 评论点赞接口
                  path('comments/<int:pk>/like/', CommentLikeView.as_view(), name='comment-like'),
                  # 删除评论接口
                  path('comments/<int:pk>/', CommentDestroyView.as_view(), name='comment-detail'),
                  # 不喜欢的评论
                  path('comments/<int:pk>/dislike/', CommentDislikeView.as_view(), name='comment-dislike'),
                  # 获取更多子评论
                  path('comments/<int:root_id>/subcomments/', SubCommentListView.as_view(), name='sub-comments'),
                  # 笔记搜索（查询条件：标题，类别，作者，正文，内容概要），按类别搜索与下面的“按类别的热度排序”有一定的重合）
                  path('notes/search/', NoteSearchView.as_view(), name='note-search'),
                  # 笔记首页展示热门笔记Top10，推荐使用第一个
                  path('notes/Top/', TopNotesView.as_view(), name='top-notes'),
                  # path('notes/Top_10/', Top10NotesView.as_view(), name='top10-notes'),
                  # 按类别的热度排序
                  path('notes/category/<str:category>/page/<int:page_number>/', NotesByCategoryView.as_view(), name='notes_by_category'),
                  # 笔记预览
                  path('notes/<int:note_id>/preview/', preview_note, name='note-preview'),
                  # AI笔记总结
                  path('notes/ai_conclude/', spark_lite, name='note-ai_conclude'),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)