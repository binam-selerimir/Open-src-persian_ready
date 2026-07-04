"""
posts/sitemaps.py
=================
Sitemap classes for the posts application.

Registered in myproject/urls.py and served at /sitemap.xml.
Requires 'django.contrib.sitemaps' in INSTALLED_APPS.

PostSitemap     – all visible posts, updated weekly, priority 0.8.
CategorySitemap – all categories, updated weekly, priority 0.5.
"""

from django.contrib.sitemaps import Sitemap

from .models import Category, Post


class PostSitemap(Sitemap):
    """Sitemap entry for every publicly visible post."""

    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Post.objects.published().order_by('-pub_date')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class CategorySitemap(Sitemap):
    """Sitemap entry for every category landing page."""

    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()
