"""Post CRUD, media upload, and bulk actions."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from posts.forms import PostForm
from posts.models import Category, Post, PostType
from posts.utils import classify_upload_file, save_inline_media

from ...utils import audit
from . import _admin_login_required


def _save_post(form, request):
    """Save a PostForm instance, setting publisher if missing."""
    post = form.save(commit=False)
    if not post.publisher:
        post.publisher = request.user
    post.save()
    form.save_m2m()
    return post


@_admin_login_required
def upload_post_media(request):
    """AJAX endpoint: upload inline media for the post editor."""
    if request.method != 'POST':
        return JsonResponse({'error': _('POST required.')}, status=405)
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': _('No file provided.')}, status=400)
    url, error = save_inline_media(uploaded)
    if error:
        return JsonResponse({'error': error}, status=400)
    file_type = classify_upload_file(uploaded.name) or 'unknown'
    return JsonResponse({'url': url, 'type': file_type, 'name': uploaded.name})


@_admin_login_required
def admin_new_post(request):
    """Create a new post."""
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = _save_post(form, request)
        audit(request, "POST_CREATE", f"Created post #{post.id}: {post.title}")
        messages.success(request, _('Post created successfully.'))
        return redirect('accounts:admin_posts')
    return render(request, 'accounts/admin_new_post.html', {
        'form': form, 'post': None, 'active_tab': 'new_post',
    })


@_admin_login_required
def admin_posts(request):
    """Paginated post list with search, filters, sort, bulk actions."""
    from comments.models import Comment  # local import: accounts <-> comments circular dependency
    qs = Post.objects.select_related('category', 'publisher', 'post_type').annotate(
        comment_count=Count('comments'),
        pending_comment_count=Count('comments', filter=Q(comments__is_approved=False)),
    ).only(
        'id', 'title', 'slug', 'pub_date', 'is_visible', 'author_name',
        'category__id', 'category__name_en', 'publisher__id', 'publisher__username',
        'post_type__id', 'post_type__name_en',
    )

    if not request.user.is_superuser:
        qs = qs.filter(publisher=request.user)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author_name__icontains=q))

    for field, value in {
        'category__slug': request.GET.get('category'),
        'post_type__slug': request.GET.get('type'),
    }.items():
        if value:
            qs = qs.filter(**{field: value})

    is_visible = request.GET.get('visible')
    if is_visible == '1':
        qs = qs.filter(is_visible=True)
    elif is_visible == '0':
        qs = qs.filter(is_visible=False)

    sort = request.GET.get('sort', 'pub_date')
    direction = request.GET.get('dir', 'desc')
    if direction not in {'asc', 'desc'}:
        direction = 'desc'
    sort_field = sort if direction == 'asc' else f'-{sort}'
    if sort in {'pub_date', 'title', 'category__name_en'}:
        qs = qs.order_by(sort_field)

    if request.method == 'POST' and 'bulk_action' in request.POST:
        action = request.POST.get('bulk_action')
        raw_pks = request.POST.getlist('selected_posts')
        pks = [int(pk) for pk in raw_pks if pk.isdigit()]
        if pks:
            bulk_qs = Post.objects.filter(pk__in=pks)
            if not request.user.is_superuser:
                bulk_qs = bulk_qs.filter(publisher=request.user)
            if action == 'publish':
                count = bulk_qs.update(is_visible=True)
                audit(request, 'POST_EDIT', f'Bulk published {count} posts')
                messages.success(request, _('Selected posts published.'))
            elif action == 'hide':
                count = bulk_qs.update(is_visible=False)
                audit(request, 'POST_EDIT', f'Bulk hidden {count} posts')
                messages.success(request, _('Selected posts hidden.'))
            elif action == 'delete':
                try:
                    count = bulk_qs.count()
                    bulk_qs.delete()
                    audit(request, 'POST_DELETE', f'Bulk deleted {count} posts')
                    messages.success(request, _('Selected posts deleted.'))
                except ProtectedError:
                    messages.error(request, _(
                        'Some posts could not be deleted because they are '
                        'referenced by protected related items.'
                    ))
        elif raw_pks and not pks:
            messages.warning(request, _('No valid posts selected.'))
        return redirect(request.get_full_path())

    page_obj = Paginator(qs, 25).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_posts.html', {
        'posts': page_obj, 'page_obj': page_obj, 'active_tab': 'posts',
        'q': q, 'sort': sort, 'dir': direction,
        'categories': Category.objects.all(),
        'post_types': PostType.objects.all(),
        'active_cat': request.GET.get('category', ''),
        'active_type': request.GET.get('type', ''),
        'active_visible': is_visible or '',
        'is_superuser': request.user.is_superuser,
    })


@_admin_login_required
def admin_edit_post(request, pk):
    """Edit an existing post with per-post comment management."""
    post = get_object_or_404(Post, pk=pk)
    if not request.user.is_superuser and post.publisher != request.user:
        return render(request, '403.html', status=403)
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == 'POST' and 'form_type' not in request.POST:
        if form.is_valid():
            new_md = form.cleaned_data.get('body_md_file')
            old_md = post.body_md_file
            if new_md and old_md and new_md != old_md:
                try:
                    old_md.delete(save=False)
                except Exception:
                    pass
            post = _save_post(form, request)
            audit(request, "POST_EDIT", f"Edited post #{post.id}")
            messages.success(request, _('Post updated successfully.'))
            return redirect('accounts:admin_posts')

    from comments.models import Comment  # local import: accounts <-> comments circular dependency
    post_comments = Comment.objects.filter(post=post).order_by('-created_at')

    if request.method == 'POST' and request.POST.get('form_type') == 'comment_action':
        comment_pks = [int(pk) for pk in request.POST.getlist('selected_comments') if pk.isdigit()]
        action = request.POST.get('comment_action')
        if comment_pks:
            if action == 'approve':
                Comment.objects.filter(pk__in=comment_pks, post=post).update(is_approved=True)
                messages.success(request, _('Selected comments approved.'))
            elif action == 'reject':
                Comment.objects.filter(pk__in=comment_pks, post=post).update(is_approved=False)
                messages.success(request, _('Selected comments rejected.'))
            elif action == 'delete':
                Comment.objects.filter(pk__in=comment_pks, post=post).delete()
                messages.success(request, _('Selected comments deleted.'))
        elif request.POST.getlist('selected_comments') and not comment_pks:
            messages.warning(request, _('No valid comments selected.'))
        return redirect(f"{request.path}#comments-section")

    return render(request, 'accounts/admin_edit_post.html', {
        'form': form, 'post': post, 'active_tab': 'posts',
        'post_comments': post_comments,
    })


@_admin_login_required
def admin_delete_post(request, pk):
    """Delete a post with confirmation."""
    post = get_object_or_404(Post, pk=pk)
    if not request.user.is_superuser and post.publisher != request.user:
        return render(request, '403.html', status=403)
    if request.method == 'POST':
        post_title = post.title
        post_id = post.id
        post.delete()
        audit(request, "POST_DELETE", f"Deleted post #{post_id}: {post_title}")
        messages.success(request, _('Post deleted.'))
        return redirect('accounts:admin_posts')
    return render(request, 'accounts/admin_delete_post.html', {
        'post': post, 'active_tab': 'posts',
    })


__all__ = [
    'upload_post_media', 'admin_new_post', 'admin_posts',
    'admin_edit_post', 'admin_delete_post',
]
