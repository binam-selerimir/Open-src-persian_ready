"""
posts/admin.py
==============
Django admin registrations for post-related models, styled with Unfold.

All classes use prepopulated_fields to auto-fill slug from the name/title
field as the user types, following Django best practices for URL-safe identifiers.

PostAdmin includes:
  - list_filter  for narrowing by category, type, visibility, and date.
  - search_fields for keyword search across title, body, and author_name.
  - filter_horizontal for the M2M tags field (more usable than a plain <select>).
  - date_hierarchy for date-based drill-down navigation.
  - readonly_fields for auto-managed timestamps.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin

from .forms import PostForm
from .models import Category, Post, PostType, Subcategory, Tag


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    """Admin for top-level content categories."""
    list_display = ('name_en', 'name_fa', 'slug', 'order')
    prepopulated_fields = {'slug': ('name_en',)}


@admin.register(Subcategory)
class SubcategoryAdmin(ModelAdmin):
    """Admin for subcategories — shows parent category for context."""
    list_display = ('category', 'name_en', 'name_fa')
    list_select_related = ('category',)
    prepopulated_fields = {'slug': ('name_en',)}


@admin.register(PostType)
class PostTypeAdmin(ModelAdmin):
    """Admin for post type labels (e.g. Translation, Original EN)."""
    list_display = ('name_en', 'name_fa', 'slug', 'accent_color', 'order')
    prepopulated_fields = {'slug': ('name_en',)}


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    """Admin for free-form post tags."""
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Post)
class PostAdmin(ModelAdmin):
    """Admin for the primary Post model with full search and filter support."""
    form = PostForm
    list_display = ('title', 'category', 'post_type', 'publisher', 'pub_date', 'is_visible')
    list_filter = ('category', 'subcategory', 'post_type', 'is_visible', 'pub_date')
    list_select_related = ('category', 'subcategory', 'post_type', 'publisher')
    search_fields = ('title', 'author_name', 'body', 'summary')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('tags',)
    raw_id_fields = ('publisher',)
    date_hierarchy = 'pub_date'
    readonly_fields = ('created_at', 'updated_at')
