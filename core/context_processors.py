"""
core/context_processors.py
===========================
Custom template context processor that injects site-wide navigation data
into every template rendered by Django's template engine.

Registered in settings.TEMPLATES['OPTIONS']['context_processors'] as
'core.context_processors.global_context'.

Injected variables
------------------
categories   : QuerySet of all Category objects with subcategories prefetched,
               used to render the category navigation menu.
latest_posts : The 5 most recently published visible posts, used in sidebar
               widgets and the "Latest" section in the base template.
nav_pages    : Pages with show_in_nav=True ordered by nav_order, rendered
               as links in the top navigation bar.

Error handling
--------------
If any DB query raises an exception (e.g. during initial migrations before
tables exist), the processor logs the error and returns empty lists so
Django can still render templates without crashing.

Caching
-------
Navigation data is cached for _CONTEXT_CACHE_TTL seconds to avoid
hitting the database on every single request (including admin, 404 pages, etc.).

LocMemCache (development fallback) is per-process — cache.delete() in signals
only invalidates the current worker's cache. Other workers keep stale data until
TTL expires. Set REDIS_URL in production for shared cache invalidation across
all Gunicorn workers.
"""

import logging

from django.core.cache import cache
from django.conf import settings
from django.db import models
from django.utils import timezone

from .models import Page, SiteAlert
from posts.models import Category, Post

# Use the module-level logger so exceptions are traceable in the logs
# without crashing the request/response cycle.
logger = logging.getLogger(__name__)

# Navigation data is cached under this key for _CONTEXT_CACHE_TTL seconds.
_CONTEXT_CACHE_KEY = 'global_nav_context'
# Use shorter TTL for LocMemCache (dev) since cache.delete() is per-process.
# In production with Redis, cache.delete() works across workers, so 5min is fine.
# Check for the specific Django 6 RedisCache backend path rather than a fragile
# substring match on the backend class name.
_CONTEXT_CACHE_TTL = 300 if 'redis' in getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', '').lower() else 60


def global_context(request):
    """
    Return a dict of context variables available in every template.

    Results are cached for 5 minutes so repeated requests don't hit the
    database.  On a cache miss, three queries are executed and the result is
    stored; subsequent requests within the TTL window are served from cache.
    """
    try:
        ctx = cache.get(_CONTEXT_CACHE_KEY)
        if ctx is None:
            ctx = {
                'categories': list(
                    Category.objects.prefetch_related('subcategories').all()
                ),
                'latest_posts': list(
                    Post.objects.published()
                        .select_related('category', 'post_type', 'publisher')
                        .only('id', 'title', 'slug', 'pub_date', 'cover_image',
                              'category__id', 'category__name_en', 'category__slug',
                              'post_type__id', 'post_type__name_en', 'post_type__accent_color',
                              'publisher__id', 'publisher__username')[:5]
                ),
                'nav_pages': list(
                    Page.objects.filter(show_in_nav=True).order_by('nav_order')
                ),
            }
            # Use add() to prevent cache stampede — only the first caller writes.
            cache.add(_CONTEXT_CACHE_KEY, ctx, _CONTEXT_CACHE_TTL)
        return ctx
    except Exception:
        # Log the full traceback but don't let a DB error crash every page.
        logger.exception('global_context failed to load navigation data')
        return {'categories': [], 'latest_posts': [], 'nav_pages': []}


def site_alert(request):
    """
    Inject the active site alert into every template context.

    Attaches ``localised_title`` and ``localised_message`` to the alert
    object so templates can render the correct language version.

    Returns {'site_alert': alert} if a visible, non-dismissed alert exists,
    otherwise {'site_alert': None}. Not cached — admin changes take effect immediately.
    """
    try:
        now = timezone.now()
        alert = (
            SiteAlert.objects
            .filter(is_active=True)
            .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
            .order_by('-created_at')
            .first()
        )
        if alert:
            cookie_key = f'alert_dismissed_{alert.pk}'
            if request.COOKIES.get(cookie_key):
                alert = None
            else:
                # Attach localised text based on the current request language.
                from django.utils import translation
                lang = translation.get_language()
                alert.localised_title = alert.get_localised_title(lang)
                alert.localised_message = alert.get_localised_message(lang)
        return {'site_alert': alert}
    except Exception:
        logger.exception('site_alert context processor failed')
        return {'site_alert': None}
