from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from notesmanage.views import (
    UserNotesView,  NoteRetrieveUpdateDestroyView,
    NoteLikeView,  NoteSearchView, CommentDestroyView, CommentLikeView,
    TopNotesView,  NoteListView, NotesByCategoryView,
    UserLikedNotesView, CommentListCreateView, CommentDislikeView, SubCommentListView,
    UserFavoriteNotesView, NoteFavoriteView, FollowToggleView, FollowedUsersListView,
    FollowersListView, CoverThumbnailView
)
from .ai_conclude import spark_lite
from rest_framework.routers import DefaultRouter
from .views import DraftNoteViewSet, PublishedNoteViewSet

# 使用 DRF 的 DefaultRouter 自动注册 ViewSet 路由
router = DefaultRouter()
# 草稿笔记路由：支持 list/create/retrieve/update/destroy
# 自定义操作：
#   POST   drafts/{pk}/regenerate_covers/   重新生成 AI 候选封面
#   PATCH  drafts/{pk}/select_cover/        选择封面（上传或生成）
router.register(r'drafts', DraftNoteViewSet, basename='draft')

# 正式笔记路由：支持 list/create/retrieve/update/destroy
# 自定义操作：
#   POST   notes/publish/                  从草稿发布为正式笔记，需要传 draft_id
router.register(r'notes', PublishedNoteViewSet, basename='note')

urlpatterns = [
                  # 通过表单实现的笔记上传页面
                  # path('create/', views.create_note, name='create_note'),
                  # 无保护的笔记信息列表（测试用）
                  path('notes_list/', NoteListView.as_view(), name='note-list'),
                  # 访问某一用户的所有（公开）笔记
                  path('user/<int:user_id>/notes/', UserNotesView.as_view(), name='user-notes'),
                  # 使用视图逻辑的用户创建笔记
                  # path('notes/create', NoteCreateView.as_view(), name='note-list-create'),
                  # 封面图预览
                  path('notes/<int:note_id>/covers/thumbnail/<str:filename>/',CoverThumbnailView.as_view(), name='cover-thumbnail'),
                  # 多功能，集笔记访问（客人用户访问时read_only，同时浏览数增加；笔记所有者访问时可以对笔记进行修改和删除）
                  path('notes/<int:pk>/', NoteRetrieveUpdateDestroyView.as_view(), name='note-retrieve-update-destroy'),
                  # 关注功能
                  path('follow/<int:pk>/', FollowToggleView.as_view(), name='follow-toggle'),
                  # 关注列表
                  path('following/', FollowedUsersListView.as_view(), name='followed-users'),
                  # 粉丝列表
                  path('followers/', FollowersListView.as_view(), name='followers'),
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
                  # path('notes/<int:note_id>/preview/', preview_note, name='note-preview'),
                  # AI笔记总结
                  path('notes/ai_conclude/', spark_lite, name='note-ai_conclude'),
                  path('', include(router.urls)),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


"""
GET /api/drafts/ 草稿列表

POST /api/drafts/ 新建草稿

GET /api/drafts/{pk}/ 获取草稿详情

PUT /api/drafts/{pk}/ 更新草稿（整体替换）

PATCH /api/drafts/{pk}/ 更新草稿（部分字段）
**草稿在没发布前可以随时更新，PUT/PATCH 都行**

DELETE /api/drafts/{pk}/ 删除草稿

POST /api/drafts/{pk}/regenerate_covers/ 重新生成 AI 候选封面

PATCH /api/drafts/{pk}/select_cover/ 选择封面

GET /api/notes/ 正式笔记列表

POST /api/notes/ 新建正式笔记（如果需要）

GET /api/notes/{pk}/ 获取正式笔记详情

PUT /api/notes/{pk}/ 更新正式笔记

PATCH /api/notes/{pk}/ 更新正式笔记（可用于修改封面、正文等）

DELETE /api/notes/{pk}/ 删除正式笔记

POST /api/notes/publish/ 从草稿发布正式笔记（请求体需 { "draft_id": <id> }）
"""