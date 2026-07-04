"""
search/urls.py
==============
URL patterns for the search application (namespace: 'search').

Endpoints
---------
/search/         – Main search page with form and results (search_page view).
/search/results/ – Permanent redirect to /search/ (with query string preserved).
                   Keeps old bookmarks working if the URL was previously /results/.

The redirect uses RedirectView with query_string=True so all ?q=... filter
parameters are forwarded to the canonical /search/ URL.
"""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'search'

urlpatterns = [
    # Primary search endpoint — handles both GET (form display) and
    # GET with params (search execution + results display).
    path('', views.search_page, name='search'),
    # Legacy redirect: /search/results/?q=foo → /search/?q=foo
    path('results/', RedirectView.as_view(
        pattern_name='search:search', query_string=True, permanent=True
    )),
]
