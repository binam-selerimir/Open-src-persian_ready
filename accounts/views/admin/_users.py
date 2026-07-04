"""User management (superuser only)."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from ...utils import audit
from ._common import _safe_int

User = get_user_model()


@login_required(login_url='accounts:login')
def admin_users(request):
    """Toggle is_active and is_site_admin for users (superuser only)."""
    if not request.user.is_superuser:
        return render(request, '403.html', status=403)

    if request.method == 'POST':
        user_id = _safe_int(request.POST.get('user_id'), default=None)
        if user_id is None:
            messages.error(request, _('Invalid user ID.'))
            return redirect('accounts:admin_users')
        user = get_object_or_404(User, pk=user_id)
        if user == request.user:
            messages.error(request, _('You cannot modify your own account from here.'))
            return redirect('accounts:admin_users')
        if user.is_superuser:
            messages.error(request, _('You cannot modify a superuser account from here.'))
            return redirect('accounts:admin_users')
        if 'toggle_active' in request.POST:
            with transaction.atomic():
                target = User.objects.select_for_update().get(pk=user.pk)
                old_value = target.is_active
                if old_value and target.is_site_admin and User.objects.filter(
                    is_site_admin=True, is_active=True
                ).count() <= 1:
                    messages.error(request, _('Cannot deactivate the last active site admin.'))
                    return redirect('accounts:admin_users')
                target.is_active = not target.is_active
                target.save(update_fields=['is_active'])
            audit(request, "ROLE_CHANGE",
                  f"Toggle is_active: {old_value} -> {target.is_active} for user '{target.username}'")
            messages.success(request, _('User "%s" active status updated.') % target.username)
        elif 'toggle_site_admin' in request.POST:
            with transaction.atomic():
                target = User.objects.select_for_update().get(pk=user.pk)
                if target.is_site_admin and User.objects.filter(is_site_admin=True).count() <= 1:
                    messages.error(request, _('Cannot revoke admin from the last site admin.'))
                    return redirect('accounts:admin_users')
                old_value = target.is_site_admin
                target.is_site_admin = not target.is_site_admin
                target.save(update_fields=['is_site_admin'])
            audit(request, "ROLE_CHANGE",
                  f"Toggle is_site_admin: {old_value} -> {target.is_site_admin} for user '{target.username}'")
            messages.success(request, _('User "%s" site admin status updated.') % target.username)
        return redirect('accounts:admin_users')

    qs = User.objects.all().order_by('username')
    page_obj = Paginator(qs, 50).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_users.html', {
        'users': page_obj, 'page_obj': page_obj, 'active_tab': 'users',
    })


__all__ = ['admin_users']
