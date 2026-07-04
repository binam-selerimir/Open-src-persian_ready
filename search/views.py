"""
search/views.py
===============
Full-text search across posts, with support for multiple simultaneous filters.

search_page
-----------
Renders an empty search form on first load (no ?q= or filter params).
When any filter is present, executes the search and paginates results.

Supported query parameters
--------------------------
q              – keyword searched against title, body, summary, author_name
type           – filter by PostType slug
category       – filter by Category slug
subcategory    – filter by Subcategory slug (cascades from category filter)
tag            – filter by Tag slug
date_from      – lower bound (YYYY-MM-DD); inclusive
date_to        – upper bound (YYYY-MM-DD); inclusive

Performance notes
-----------------
* is_visible=True is always enforced so unpublished posts never appear in results.
* select_related() avoids N+1 queries when the template accesses post.category,
  post.subcategory, and post.post_type for each result row.
* .distinct() is required when filtering via ManyToManyField (tags__slug=) to
  prevent duplicate rows when a post has multiple matching tags.
"""

from datetime import date

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from accounts.utils import check_rate_limit
from posts.models import Category, Post, PostType, Subcategory, Tag

RESULTS_PER_PAGE = 20
MAX_Q_LENGTH = 200


def _parse_date(value):
    """
    Return a date object if value is a valid YYYY-MM-DD string, else None.

    Using date.fromisoformat() is safe here because we catch ValueError and
    return None for any malformed input, so no exception reaches the user.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def search_page(request):
    """
    Main search view — renders the search form and executes queries.

    The form is submitted via GET so results are bookmarkable/shareable
    and the browser back button restores the query without resubmission.

    When `searched` is False (no parameters provided), an empty queryset
    is passed to the template to skip the "N results found" count display.
    """
    # Rate-limit search to prevent automated abuse (30 requests/min per IP).
    if not check_rate_limit(request, 'search', limit=30):
        from django.http import HttpResponse
        return HttpResponse('Too many requests. Please slow down.', status=429)

    # Collect all filter parameters from the query string.
    _FILTER_KEYS = ('q', 'type', 'category', 'subcategory', 'tag', 'date_from', 'date_to')
    filters = {k: request.GET.get(k, '').strip() for k in _FILTER_KEYS}
    q = filters['q'][:MAX_Q_LENGTH] if filters['q'] else ''
    post_type = filters['type']
    category_slug = filters['category']
    subcategory_slug = filters['subcategory']
    tag_slug = filters['tag']
    date_from = filters['date_from']
    date_to = filters['date_to']

    searched = any(filters.values())

    if searched:
        results = Post.objects.published().select_related(
            'category', 'subcategory', 'post_type',
        ).prefetch_related('tags').only(
            'id', 'title', 'slug', 'pub_date', 'summary', 'cover_image', 'author_name',
            'category__id', 'category__name_en', 'category__slug',
            'subcategory__id', 'subcategory__name_en', 'subcategory__slug',
            'post_type__id', 'post_type__name_en', 'post_type__accent_color',
        )

        # Full-text keyword search: OR across multiple fields.
        if q:
            results = results.filter(
                Q(title__icontains=q)
                | Q(body__icontains=q)
                | Q(summary__icontains=q)
                | Q(author_name__icontains=q)
            )

        # Taxonomy / format filters.
        if post_type:
            results = results.filter(post_type__slug=post_type)
        if category_slug:
            results = results.filter(category__slug=category_slug)
        if subcategory_slug:
            results = results.filter(subcategory__slug=subcategory_slug)

        # Parse date strings — invalid input returns None and is silently ignored.
        parsed_from = _parse_date(date_from)
        parsed_to = _parse_date(date_to)

        # Tag filter via ManyToManyField; .distinct() prevents duplicate rows.
        if tag_slug:
            results = results.filter(tags__slug=tag_slug)

        # Date range filtering: pub_date__date converts the DateTimeField to a date
        # for comparison, ignoring the time component.
        if parsed_from:
            results = results.filter(pub_date__date__gte=parsed_from)
        if parsed_to:
            results = results.filter(pub_date__date__lte=parsed_to)

        # Order by newest first; distinct() required after ManyToMany filter.
        results = results.order_by('-pub_date').distinct()
        page_obj = Paginator(results, RESULTS_PER_PAGE).get_page(
            request.GET.get('page', 1)
        )
        total = page_obj.paginator.count
    else:
        # No search submitted — pass empty results so the template shows the form only.
        results = Post.objects.none()
        total = 0
        page_obj = Paginator(results, RESULTS_PER_PAGE).get_page(1)

    # Cascade subcategories when a category is selected so the sub-filter
    # dropdown is populated with only relevant options.
    subcategories = (
        Subcategory.objects.filter(category__slug=category_slug)
        if category_slug else Subcategory.objects.none()
    )

    return render(request, 'search/search.html', {
        'results': page_obj,
        'page_obj': page_obj,
        'total': total,
        'searched': searched,
        # Pass filter values back so the form fields retain their state.
        'q': q,
        'post_type': post_type,
        'category_slug': category_slug,
        'subcategory_slug': subcategory_slug,
        'tag_slug': tag_slug,
        'date_from': date_from,
        'date_to': date_to,
        # Populate filter dropdowns.
        'categories': Category.objects.all(),
        'post_types': PostType.objects.all(),
        'subcategories': subcategories,
        'tags': Tag.objects.order_by('name')[:100],
    })
