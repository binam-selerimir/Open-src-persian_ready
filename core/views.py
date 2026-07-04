"""
core/views.py
=============
Views for the core application: homepage, static flat pages, About page,
and the custom 404 handler.

Views defined here
------------------
home          – renders the homepage with the 5 latest visible posts.
page_detail   – renders a single flat Page object looked up by slug.
about         – renders the static About page template.
page_not_found – custom 404 handler registered as handler404 in urls.py.
"""

from django.shortcuts import get_object_or_404, render

from posts.models import Post

from .models import Page


def home(request):
    """
    Render the site homepage.

    Passes the 5 most recently published visible posts to the template
    for display in the "Latest News" section.
    """
    return render(request, 'core/home.html', {
        'latest_news': Post.objects.published()[:5],
    })


def page_detail(request, slug):
    """
    Render a flat content page identified by its unique slug.

    Returns 404 if no Page with the given slug exists.
    """
    return render(request, 'core/page_detail.html', {
        'page': get_object_or_404(Page, slug=slug),
    })


def about(request):
    """
    Render the About page.

    First checks for a Page object with slug='about' in the database.
    If found, renders it via page_detail.html (admin-editable via /admin/core/page/).
    If not found, falls back to the static about.html template.
    """
    page = Page.objects.filter(slug='about').first()
    if page:
        return render(request, 'core/page_detail.html', {'page': page})
    return render(request, 'core/about.html', {})


def page_not_found(request, exception=None):
    """
    Custom 404 handler — registered as handler404 in myproject/urls.py.

    Renders 404.html with an explicit 404 status code.  Django's default
    handler would work, but this allows the template to use the site's
    base layout with the navigation intact.
    """
    return render(request, '404.html', status=404)


def server_error(request, exception=None):
    """
    Custom 500 handler — registered as handler500 in myproject/urls.py.

    Renders 500.html with the site layout for a branded error page.
    Accepts an optional exception parameter as required by Django's handler500
    signature (Django >= 2.0 passes the exception as a keyword argument).

    Falls back to a hard-coded response if template rendering fails
    (e.g. during a database outage when context processors cannot execute).
    """
    try:
        return render(request, '500.html', status=500)
    except Exception:
        from django.http import HttpResponse
        return HttpResponse(
            '<!DOCTYPE html><html><head><title>500</title></head>'
            '<body><h1>500 Internal Server Error</h1>'
            '<p>Something went wrong. Please try again later.</p>'
            '</body></html>',
            status=500,
            content_type='text/html',
        )
