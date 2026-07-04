"""Comment management for admin panel."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from ...utils import audit
from ._common import _admin_login_required


@_admin_login_required
def admin_comments(request):
    """Manage comments with bulk actions. Staff sees only own posts' comments."""
    from comments.models import Comment

    qs = Comment.objects.select_related('post').order_by('-created_at')

    if not request.user.is_superuser:
        qs = qs.filter(post__publisher=request.user)

    status_filter = request.GET.get('status', '')
    if status_filter == 'pending':
        qs = qs.filter(is_approved=False)
    elif status_filter == 'approved':
        qs = qs.filter(is_approved=True)

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        raw_pks = request.POST.getlist('selected_comments')
        pks = [int(pk) for pk in raw_pks if pk.isdigit()]
        if pks:
            comment_qs = Comment.objects.filter(pk__in=pks)
            if not request.user.is_superuser:
                comment_qs = comment_qs.filter(post__publisher=request.user)
            if action == 'approve':
                count = comment_qs.update(is_approved=True)
                audit(request, 'POST_EDIT', f'Bulk approved {count} comments')
                messages.success(request, _('Selected comments approved.'))
            elif action == 'reject':
                count = comment_qs.update(is_approved=False)
                audit(request, 'POST_EDIT', f'Bulk rejected {count} comments')
                messages.success(request, _('Selected comments rejected.'))
            elif action == 'delete':
                count = comment_qs.delete()[0]
                audit(request, 'POST_DELETE', f'Bulk deleted {count} comments')
                messages.success(request, _('Selected comments deleted.'))
        elif raw_pks and not pks:
            messages.warning(request, _('No valid comments selected.'))
        return redirect(request.get_full_path())

    page_obj = Paginator(qs, 25).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_comments.html', {
        'comments': page_obj, 'page_obj': page_obj, 'active_tab': 'comments',
        'status_filter': status_filter,
    })


__all__ = ['admin_comments']
