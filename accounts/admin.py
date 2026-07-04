"""
accounts/admin.py
=================
Django admin registrations for accounts models, styled with the Unfold theme.

CustomUserAdmin  – extends Django's built-in UserAdmin with the extra fields
                   defined in CustomUser (is_site_admin, bio, avatar, website).

UserProfileAdmin – exposes UserProfile in the admin with display_name and
                   headline visible in the list view.

AuditLogAdmin    – read-only audit trail view.  Add and change permissions
                   are removed so log entries cannot be created or modified
                   through the UI, preserving the integrity of the audit trail.
                   All fields are listed as readonly_fields for the same reason.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from unfold.admin import ModelAdmin

from .models import AuditLog, CustomUser, UserProfile

from accounts.models import Certificate, UserCertificate


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin, ModelAdmin):
    """Admin class for the custom user model.

    Inherits the full UserAdmin field layout and appends a 'Site Role' section
    with the additional fields specific to CustomUser.
    """
    fieldsets = UserAdmin.fieldsets + (
        ('Site Role', {'fields': ('is_site_admin', 'bio_en', 'bio_fa', 'avatar', 'website')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_site_admin')


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    """Admin class for user profile companion records."""
    list_display = ('user', 'display_name', 'headline_en')


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    """
    Read-only admin view for the audit log.

    All standard add/change permissions are disabled so this log functions
    as an immutable record of security and content events.
    date_hierarchy provides quick date-based navigation.
    """
    list_display  = ('created_at', 'user', 'action', 'ip_address', 'description')
    list_filter   = ('action',)
    search_fields = ('user__username', 'ip_address', 'description')
    date_hierarchy = 'created_at'
    list_select_related = ('user',)
    readonly_fields = ('created_at', 'user', 'action', 'ip_address', 'description')

    def has_add_permission(self, request):
        """Prevent creating audit log entries via the admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing audit log entries via the admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting audit log entries via the admin."""
        return False


@admin.register(Certificate)
class CertificateAdmin(ModelAdmin):
    list_display = ['name', 'accent_color', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'name_fa']
    readonly_fields = ['created_at', 'updated_at', 'created_by']

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserCertificate)
class UserCertificateAdmin(ModelAdmin):
    list_display = ['user', 'certificate', 'granted_by', 'granted_at', 'is_visible']
    list_filter = ['certificate', 'is_visible']
    search_fields = ['user__username', 'certificate__name']
    readonly_fields = ['granted_at', 'granted_by']

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)
