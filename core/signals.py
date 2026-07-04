"""
core/signals.py
===============
Django signals that invalidate the global navigation cache when
content-affecting models are saved or deleted.

The context processor (core/context_processors.py) caches categories,
latest posts, and nav pages for 5 minutes. Without these signals,
changes to posts, categories, or pages would not appear in navigation
until the cache expires.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_CONTEXT_CACHE_KEY = 'global_nav_context'


def _invalidate_nav_cache(sender, **kwargs):
    """Delete the global navigation cache entry."""
    from django.core.cache import cache
    cache.delete(_CONTEXT_CACHE_KEY)
    logger.debug('Nav cache invalidated by %s signal', sender.__name__)


# Connect to all three models that affect navigation.
# Using weak=False ensures the receivers survive garbage collection.


@receiver(post_save, sender='posts.Post')
def _on_post_save(sender, **kwargs):
    _invalidate_nav_cache(sender)


@receiver(post_delete, sender='posts.Post')
def _on_post_delete(sender, **kwargs):
    _invalidate_nav_cache(sender)


@receiver(post_save, sender='posts.Category')
def _on_category_save(sender, **kwargs):
    _invalidate_nav_cache(sender)


@receiver(post_delete, sender='posts.Category')
def _on_category_delete(sender, **kwargs):
    _invalidate_nav_cache(sender)


@receiver(post_save, sender='core.Page')
def _on_page_save(sender, **kwargs):
    _invalidate_nav_cache(sender)


@receiver(post_delete, sender='core.Page')
def _on_page_delete(sender, **kwargs):
    _invalidate_nav_cache(sender)
