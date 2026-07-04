from django.urls import path, re_path

from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.forum_index, name='index'),
    path('new/', views.new_board, name='new_board'),
    path('upload-media/', views.upload_forum_media, name='upload_media'),
    re_path(r'^(?P<board_slug>[\w\-]+)/$', views.board_detail, name='board_detail'),
    re_path(r'^(?P<board_slug>[\w\-]+)/new/$', views.new_thread, name='new_thread'),
    re_path(r'^(?P<board_slug>[\w\-]+)/(?P<slug>[\w\-]+)/$', views.thread_detail, name='thread_detail'),
    path('post/<int:pk>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:pk>/delete/', views.delete_post, name='delete_post'),
    path('thread/<int:pk>/reply/', views.reply, name='reply'),
    path('thread/<int:pk>/delete/', views.delete_thread, name='delete_thread'),
    path('thread/<int:pk>/sticky/', views.toggle_sticky, name='toggle_sticky'),
    path('thread/<int:pk>/close/', views.toggle_close, name='toggle_close'),
]
