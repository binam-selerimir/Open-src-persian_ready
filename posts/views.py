"""
posts/views.py
==============
Public-facing views for browsing and reading posts.

Views defined here
------------------
post_list         – paginated list of all visible posts; supports filtering
                    by category, subcategory, post type, and tag via GET params.
category_detail   – posts filtered to a single category.
subcategory_detail – posts filtered to a single subcategory within a category.
post_detail       – full article view for a single post, with related posts sidebar.
subcategories_json – AJAX endpoint that returns subcategories for a given category;
                     used by the post-editor panel to cascade dropdown options.
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Category, Post, PostType, Subcategory

# Number of posts shown per page in list views.
POSTS_PER_PAGE = 12


def _paginate(qs, request):
    """Convenience helper: paginate a queryset using the ?page= GET param."""
    return Paginator(qs, POSTS_PER_PAGE).get_page(request.GET.get('page', 1))


def post_list(request):
    """
    Paginated list of all visible posts.

    Supports optional GET filters:
      ?category=<slug>    – filter by category
      ?subcategory=<slug> – further filter by subcategory (must be used with category)
      ?type=<slug>        – filter by post type
      ?tag=<slug>         – filter by tag

    When a category filter is active, also fetches that category's subcategories
    so the template can render a subcategory navigation strip.
    """
    qs = Post.objects.published().select_related(
        'category', 'subcategory', 'post_type', 'publisher'
    ).prefetch_related('tags').only(
        'id', 'title', 'slug', 'pub_date', 'summary', 'cover_image', 'cover_alt', 'author_name',
        'category__id', 'category__name_en', 'category__slug',
        'subcategory__id', 'subcategory__name_en', 'subcategory__slug',
        'post_type__id', 'post_type__name_en', 'post_type__accent_color',
        'publisher__id', 'publisher__username',
    )

    # Extract filter parameters from the GET query string.
    cat_slug = request.GET.get('category', '')
    sub_slug = request.GET.get('subcategory', '')
    post_type = request.GET.get('type', '')
    tag_slug = request.GET.get('tag', '')

    # Apply each filter only when the parameter is present and non-empty.
    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)
    if sub_slug:
        qs = qs.filter(subcategory__slug=sub_slug)
    if post_type:
        qs = qs.filter(post_type__slug=post_type)
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)

    # Fetch subcategories for the active category to populate the sub-nav strip.
    if cat_slug:
        try:
            active_cat_obj = Category.objects.get(slug=cat_slug)
            active_subcategories = active_cat_obj.subcategories.all()
        except Category.DoesNotExist:
            active_subcategories = []
    else:
        active_subcategories = []

    return render(request, 'posts/post_list.html', {
        'page_obj': _paginate(qs, request),
        'post_types': PostType.objects.all(),
        'active_cat': cat_slug,
        'active_sub': sub_slug,
        'active_subcategories': active_subcategories,
        'active_type': post_type,
        'active_tag': tag_slug,   # lets template show active tag name in filter bar
    })


def category_detail(request, cat_slug):
    """
    List all visible posts belonging to a specific category.

    Returns 404 if the category slug doesn't exist.
    """
    category = get_object_or_404(Category, slug=cat_slug)
    qs = Post.objects.published().filter(category=category).select_related(
        'post_type', 'subcategory'
    ).prefetch_related('tags').defer('body')
    return render(request, 'posts/category_detail.html', {
        'category': category,
        'page_obj': _paginate(qs, request),
    })


def subcategory_detail(request, cat_slug, sub_slug):
    """
    List all visible posts in a specific subcategory.

    Both cat_slug and sub_slug must match to prevent showing a subcategory
    under the wrong parent category URL.
    """
    subcategory = get_object_or_404(Subcategory, slug=sub_slug, category__slug=cat_slug)
    qs = Post.objects.published().filter(subcategory=subcategory).select_related(
        'post_type', 'category'
    ).prefetch_related('tags')
    return render(request, 'posts/subcategory_detail.html', {
        'subcategory': subcategory,
        'page_obj': _paginate(qs, request),
    })


def post_detail(request, slug):
    """
    Full article view for a single post.

    Related posts: up to 5 other visible posts from the same category
    (excluding the current post), with tags prefetched for the sidebar.
    Returns 404 for unpublished (is_visible=False) posts.

    View counters:
    - view_count: incremented on every page load (no dedup)
    - unique_view_count: incremented once per IP address (24h cache)
    
    Comments: shows approved comments only.
    """
    post = get_object_or_404(
        Post.objects.published()
                    .select_related('post_type', 'category', 'subcategory')
                    .prefetch_related('tags'),
        slug=slug,
    )

    from accounts.utils import get_client_ip  # local import to avoid circular dependency
    from django.core.cache import cache
    from .utils import increment_view_count, increment_unique_view_count
    
    # Always increment total view count (no dedup)
    increment_view_count(post)
    
    # Increment unique view count only once per IP address (24h cache)
    client_ip = get_client_ip(request)
    cache_key = f'unique_view_{post.pk}_{client_ip}'
    UNIQUE_VIEW_CACHE_TTL = 86400  # 24 hours — must match expected dedup window
    if cache.add(cache_key, True, timeout=UNIQUE_VIEW_CACHE_TTL):
        increment_unique_view_count(post)
    
    post.refresh_from_db(fields=['view_count', 'unique_view_count'])

    recent_posts = list(
        Post.objects.published()
        .filter(category=post.category)
        .exclude(pk=post.pk)
        .select_related('post_type', 'category', 'publisher')
        .prefetch_related('tags')
        .only('id', 'title', 'slug', 'pub_date', 'cover_image',
              'category__id', 'category__name_en', 'category__slug',
              'post_type__id', 'post_type__name_en', 'post_type__accent_color',
              'publisher__id', 'publisher__username')
        .order_by('-pub_date')[:5]
    )

    approved_comments = post.comments.filter(is_approved=True).only(
        'id', 'author_name', 'body', 'created_at'
    )

    return render(request, 'posts/post_detail.html', {
        'post': post,
        'recent_posts': recent_posts,
        'approved_comments': approved_comments,
    })


@login_required(login_url='accounts:login')
def subcategories_json(request):
    """
    AJAX endpoint: return subcategories for a given category as JSON.

    Called by the post-editor panel (accounts/static/accounts/taxonomy.js)
    when the category dropdown changes, so the subcategory dropdown can
    be populated dynamically without a page reload.

    Accepts either:
      ?category=<id>    – lookup by numeric PK
      ?category_slug=<slug> – lookup by slug (preferred)

    Returns a JSON array of {id, name_en, name_fa, slug} objects.
    """
    cat_id = request.GET.get('category')
    cat_slug = request.GET.get('category_slug')

    if cat_slug:
        subs = Subcategory.objects.filter(category__slug=cat_slug)
        if not subs.exists():
            return JsonResponse({'error': 'Category not found.'}, status=400)
    elif cat_id:
        try:
            subs = Subcategory.objects.filter(category_id=int(cat_id))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid category ID.'}, status=400)
    else:
        subs = Subcategory.objects.none()

    # safe=False is required when returning a list (not a dict) as the root JSON value.
    return JsonResponse(
        list(subs.values('id', 'name_en', 'name_fa', 'slug')),
        safe=False,
    )
