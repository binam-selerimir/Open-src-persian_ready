"""
core/urls.py
============
URL patterns for the core application.

Endpoints
---------
/           – Homepage (shows latest 5 posts)
about/      – Static about page
page/<slug>/ – Dynamic flat content page (e.g. /en/page/philosophy/)

These are prefixed with a language code via i18n_patterns in myproject/urls.py,
so the full paths are e.g. /en/, /en/about/, /en/page/<slug>/.
"""

from django.urls import path

from . import views

urlpatterns = [
    # Homepage — renders core/home.html with the 5 latest visible posts.
    path('', views.home, name='home'),
    # Static About page — content lives in the template (core/about.html).
    path('about/', views.about, name='about'),
    # Dynamic flat pages — slug maps to a Page model instance.
    path('page/<slug:slug>/', views.page_detail, name='page_detail'),
]
