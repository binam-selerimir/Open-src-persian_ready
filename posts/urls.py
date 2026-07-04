"""
posts/urls.py
=============
URL patterns for the posts application (namespace: 'posts').

Endpoints
---------
/posts/                                 → post_list       (paginated post browser)
/posts/subcategories/                   → subcategories_json (AJAX for editor panel)
/posts/category/<cat_slug>/             → category_detail
/posts/category/<cat_slug>/<sub_slug>/  → subcategory_detail
/posts/<slug>/                          → post_detail

All of these patterns are prefixed with a language code via i18n_patterns
in myproject/urls.py, so the full path in production is e.g. /en/posts/<slug>/.

The <slug:...> converters allow Unicode slugs (e.g. Persian text in URLs)
because models use allow_unicode=True on their SlugFields.
"""

from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = 'posts'

urlpatterns = [
    # Main paginated post list with optional ?category=, ?type=, ?tag= filters.
    path('', views.post_list, name='post_list'),
    # RSS feed — autodiscovered by browsers via <link rel="alternate"> in base.html.
    path('feed/', LatestPostsFeed(), name='post_feed'),
    # AJAX endpoint: returns JSON array of subcategories for a given category.
    path('subcategories/', views.subcategories_json, name='subcategories_json'),
    # Category landing page — all posts in a top-level category.
    path('category/<slug:cat_slug>/', views.category_detail, name='category_detail'),
    # Subcategory landing page — posts filtered to a specific subcategory.
    path('category/<slug:cat_slug>/<slug:sub_slug>/', views.subcategory_detail, name='subcategory_detail'),
    # Full article view — slug must match a visible (is_visible=True) post.
    path('<slug:slug>/', views.post_detail, name='post_detail'),
]
