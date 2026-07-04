"""
accounts/models.py
==================
Defines the three database models that power the user and audit systems:

  CustomUser   – extends Django's AbstractUser with bilingual bio fields,
                 avatar, website, and a `is_site_admin` role flag.

  UserProfile  – a one-to-one extension that stores profile/social fields
                 that are not part of the core auth identity (headline,
                 skills, LinkedIn, GitHub, Telegram).  Created automatically
                 by the post_save signal in signals.py.

  AuditLog     – immutable ledger of security-relevant actions (login,
                 logout, post CRUD, role changes, …) written by
                 accounts.utils.audit().  All fields are read-only in the
                 Django admin.
"""

import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Index, UniqueConstraint
from django.utils.translation import gettext_lazy as _

from posts.models import _hex_color_validator


def _validate_safe_url(value):
    """Reject URLs with dangerous schemes (javascript:, data:, vbscript:) and protocol-relative URLs."""
    if value and (
        re.match(r'^\s*(javascript|data|vbscript)\s*:', value, re.I)
        or re.match(r'^\s*//', value)
    ):
        raise ValidationError(
            _('URLs with this scheme are not allowed.')
        )


class CustomUser(AbstractUser):
    """
    Site-wide user model.  Replaces auth.User via AUTH_USER_MODEL = 'accounts.CustomUser'.

    Additional fields beyond the standard AbstractUser:
        bio_en / bio_fa  – Free-text biography in English and Persian.
        avatar           – Profile picture uploaded to media/avatars/.
        website          – Personal or organisation URL.
        is_site_admin    – Grants access to the custom /panel/ admin tabs.
                           Separate from Django's `is_staff` flag so that
                           content editors don't need full Django-admin access.
    """

    email = models.EmailField(_('email address'), unique=True)
    bio_en = models.TextField(blank=True, verbose_name=_('Bio (English)'))
    bio_fa = models.TextField(blank=True, verbose_name=_('Bio (Persian)'))
    # Uploaded avatars are processed through process_avatar_image in forms.py
    # to strip EXIF data and normalise dimensions before saving.
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    website = models.URLField(blank=True, validators=[_validate_safe_url])
    is_site_admin = models.BooleanField(
        default=False,
        help_text=_('Grants access to the custom user panel admin tabs'),
    )

    def get_full_name_display(self):
        """Return 'First Last', or fall back to the username if names are not set."""
        return f"{self.first_name} {self.last_name}".strip() or self.username


class UserProfile(models.Model):
    """
    Extended profile data for each user — social links, headline, skills.

    Connected to CustomUser via a OneToOneField so that every user has at
    most one profile.  The post_save signal in signals.py creates this
    automatically when a new user is saved; edit_profile in views.py uses
    get_or_create as a guard for users created before the signal existed
    (e.g. via createsuperuser).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    # Optional display name that overrides username on the public profile page.
    display_name = models.CharField(max_length=150, blank=True)
    # Short job-title or role descriptor shown under the display name.
    headline_en = models.CharField(
        max_length=255, blank=True, help_text=_('Job title or short headline')
    )
    headline_fa = models.CharField(max_length=255, blank=True)
    # Comma-separated skill list rendered as tags on the public profile.
    skills = models.TextField(blank=True, help_text=_('Comma-separated list of skills'))
    linkedin_url = models.URLField(blank=True, validators=[_validate_safe_url])
    github_url = models.URLField(blank=True, validators=[_validate_safe_url])
    # Telegram username (without @): validated to 5–32 chars, alphanumeric + underscore.
    telegram = models.CharField(
        max_length=80,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9_]{5,32}$',
                message=_(
                    'Enter a valid Telegram username (5–32 characters, '
                    'letters, digits, and underscores only).'
                ),
            )
        ],
    )

    def __str__(self):
        return f"Profile of {self.user.username}"

    def get_skills_list(self):
        """Split the comma-separated skills string into a clean Python list."""
        if not self.skills:
            return []
        return [s.strip() for s in self.skills.split(',') if s.strip()]


class AuditLog(models.Model):
    """
    Append-only log of security and content-management events.

    Written by accounts.utils.audit() which simultaneously records to the
    database and the audit file logger (logs/audit.log).  The Django admin
    registration in admin.py removes add/change permissions so this log
    cannot be falsified through the UI.

    Captured action types
    ---------------------
    LOGIN / LOGIN_FAILED / LOGOUT   – authentication events
    PASSWORD_RESET / EMAIL_VERIFIED – account lifecycle events
    POST_CREATE / POST_EDIT / POST_DELETE – content CRUD
    ROLE_CHANGE / ADMIN_LOGIN       – privilege and admin events
    """

    ACTIONS = [
        ("LOGIN", _("Login")),
        ("LOGIN_FAILED", _("Failed Login")),
        ("LOGOUT", _("Logout")),
        ("PASSWORD_RESET", _("Password Reset")),
        ("EMAIL_VERIFIED", _("Email Verified")),
        ("POST_CREATE", _("Post Created")),
        ("POST_DELETE", _("Post Deleted")),
        ("POST_EDIT", _("Post Edited")),
        ("ROLE_CHANGE", _("Role Changed")),
        ("ADMIN_LOGIN", _("Admin Login")),
    ]

    # Nullable FK so the log is preserved even after a user is deleted.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    action = models.CharField(max_length=50, choices=ACTIONS)

    # Human-readable context, e.g. "Created post #42: My Article Title".
    description = models.TextField(blank=True)

    # Client IP at the time of the action — used for correlating suspicious activity.
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # auto_now_add makes this effectively immutable once the row is created.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Default ordering shows the most recent events first.
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.username if self.user else 'deleted user'
        return f'[{self.created_at:%Y-%m-%d %H:%M}] {self.action} — {username}'


# === Certificate System ===

class Certificate(models.Model):
    """
    A certificate template that superusers create and manage.

    Defines the badge/achievement that can be granted to users.
    Inactive certificates cannot be granted but existing grants remain.
    """

    name = models.CharField(max_length=150, unique=True)
    name_fa = models.CharField(max_length=150, blank=True, verbose_name=_('Persian name'))
    description = models.TextField(blank=True)
    description_fa = models.TextField(blank=True)
    icon = models.ImageField(
        upload_to='certificates/icons/', blank=True, null=True,
        help_text=_('Optional badge/icon image, processed to 256x256 JPEG'),
    )
    accent_color = models.CharField(
        max_length=7, default='#4f46e5', validators=[_hex_color_validator],
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_certificates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Certificate')

    def __str__(self):
        return self.name


class UserCertificate(models.Model):
    """
    A granted certificate — links a Certificate to a specific user.

    Tracks who granted it, when, and optional notes.
    Users can hide certificates from their public profile.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    certificate = models.ForeignKey(
        Certificate,
        on_delete=models.CASCADE,
        related_name='grants',
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='granted_certificates',
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['-granted_at']
        constraints = [
            UniqueConstraint(fields=['user', 'certificate'], name='unique_user_certificate'),
        ]
        indexes = [
            Index(fields=['user', 'is_visible'], name='usercert_user_visible_idx'),
        ]
        verbose_name = _('User Certificate')

    def __str__(self):
        return f"{self.user} — {self.certificate}"
