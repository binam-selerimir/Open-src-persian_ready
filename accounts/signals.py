"""
accounts/signals.py
===================
Django signal receivers for the accounts app.

sync_user_profile
-----------------
Listens to post_save on the AUTH_USER_MODEL (CustomUser) and ensures every
user always has exactly one UserProfile companion record.

* On `created=True` (new user): calls get_or_create instead of create so
  that users produced by fixtures or data migrations (which don't fire the
  signal) don't raise IntegrityError if their profile already exists.

* On `created=False` (existing user update): saves the linked profile so
  that any profile fields denormalised from user data stay in sync.
  Falls back to creating the profile if it is missing — which can happen for
  accounts created via `manage.py createsuperuser` before this signal was
  registered.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def sync_user_profile(sender, instance, created, **kwargs):
    """Ensure the UserProfile row exists; don't overwrite profile data."""
    UserProfile.objects.get_or_create(user=instance)
