"""
core/admin.py
=============
Django admin registration for the core app's Page model.

PageAdmin exposes the Page model in the admin so staff can create, edit,
and delete flat content pages (About, FAQ, Licensing Guide, etc.) without
touching the database directly.

show_in_nav and nav_order are included in list_display so administrators
can quickly scan which pages appear in the navigation and their ordering.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Page, SiteAlert


@admin.register(Page)
class PageAdmin(ModelAdmin):
    """Admin for flat content pages with bilingual fields."""
    list_display = ('title_en', 'slug', 'show_in_nav', 'nav_order')
    prepopulated_fields = {'slug': ('title_en',)}
    fieldsets = (
        (None, {
            'fields': ('slug', 'show_in_nav', 'nav_order'),
        }),
        ('English', {
            'fields': ('title_en', 'body_en'),
        }),
        ('Persian', {
            'fields': ('title_fa', 'body_fa'),
        }),
    )


@admin.register(SiteAlert)
class SiteAlertAdmin(ModelAdmin):
    """Admin for site-wide announcement banners with bilingual fields."""
    list_display = ('title_en', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    fieldsets = (
        (None, {
            'fields': ('is_active', 'expires_at'),
        }),
        ('English', {
            'fields': ('title_en', 'message_en'),
        }),
        ('Persian', {
            'fields': ('title_fa', 'message_fa'),
        }),
    )
