from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin

from .models import Board, ForumPost, Thread


@admin.register(Board)
class BoardAdmin(ModelAdmin):
    list_display = ['name_en', 'slug', 'order', 'is_active', 'created_at']
    prepopulated_fields = {'slug': ('name_en',)}
    search_fields = ['name_en', 'name_fa']


@admin.register(Thread)
class ThreadAdmin(ModelAdmin):
    list_display = [
        'title', 'board', 'author', 'is_sticky', 'is_closed',
        'is_deleted', 'reply_count', 'view_count', 'created_at',
    ]
    list_filter = ['board', 'is_sticky', 'is_closed', 'is_deleted']
    raw_id_fields = ['author']
    search_fields = ['title']
    readonly_fields = ['view_count', 'reply_count', 'created_at', 'updated_at']


@admin.register(ForumPost)
class ForumPostAdmin(ModelAdmin):
    list_display = ['pk', 'thread', 'author', 'is_first_post', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'is_first_post']
    raw_id_fields = ['author', 'thread']
    readonly_fields = ['ip_address', 'created_at', 'updated_at']
