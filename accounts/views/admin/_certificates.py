"""Certificate CRUD and grant/revoke management (superuser only)."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from ...forms import CertificateForm, GrantCertificateForm
from ...models import Certificate, UserCertificate
from ...utils import audit

logger = logging.getLogger('accounts')


@login_required(login_url='accounts:login')
def admin_certificates(request):
    """Certificate CRUD: create, edit, toggle active, delete."""
    if not request.user.is_superuser:
        return redirect('accounts:panel')

    certificates = Certificate.objects.select_related('created_by').order_by('name')
    form = CertificateForm()
    edit_form = None
    edit_cert = None
    error = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            form = CertificateForm(request.POST, request.FILES)
            if form.is_valid():
                cert = form.save(commit=False)
                cert.created_by = request.user
                if cert.icon:
                    try:
                        from posts.image_processing import process_avatar_image
                        cert.icon = process_avatar_image(cert.icon)
                    except Exception:
                        logger.exception(
                            'Failed to process certificate icon for %s', cert.name
                        )
                cert.save()
                audit(request, "POST_CREATE", f"Created certificate: {cert.name}")
                messages.success(request, _('Certificate "%s" created.') % cert.name)
                return redirect('accounts:admin_certificates')
            else:
                error = _('Fix the errors below.')

        elif action == 'edit':
            pk = request.POST.get('cert_id')
            cert = get_object_or_404(Certificate, pk=pk)
            edit_form = CertificateForm(request.POST, request.FILES, instance=cert)
            if edit_form.is_valid():
                edit_form.save()
                audit(request, "POST_EDIT", f"Edited certificate: {cert.name}")
                messages.success(request, _('Certificate "%s" updated.') % cert.name)
                return redirect('accounts:admin_certificates')

        elif action == 'delete':
            pk = request.POST.get('cert_id')
            cert = get_object_or_404(Certificate, pk=pk)
            if cert.grants.exists():
                messages.warning(
                    request,
                    _('Cannot delete "%s" — it has been granted to users. '
                      'Deactivate it instead.') % cert.name,
                )
            else:
                name = cert.name
                cert.delete()
                audit(request, "POST_DELETE", f"Deleted certificate: {name}")
                messages.success(request, _('Certificate "%s" deleted.') % name)
            return redirect('accounts:admin_certificates')

        elif action == 'toggle_active':
            pk = request.POST.get('cert_id')
            cert = get_object_or_404(Certificate, pk=pk)
            cert.is_active = not cert.is_active
            cert.save(update_fields=['is_active'])
            state = _("activated") if cert.is_active else _("deactivated")
            audit(request, 'POST_EDIT', f'Certificate {state}: {cert.name}')
            messages.success(request, _('Certificate "%s" %s.') % (cert.name, state))
            return redirect('accounts:admin_certificates')

    return render(request, 'accounts/admin_certificates.html', {
        'certificates': certificates,
        'form': form,
        'edit_form': edit_form,
        'edit_cert': edit_cert,
        'error': error,
    })


@login_required(login_url='accounts:login')
def admin_grant_certificate(request):
    """Grant or revoke certificates to/from users."""
    if not request.user.is_superuser:
        return redirect('accounts:panel')

    grants = (UserCertificate.objects
              .select_related('user', 'certificate', 'granted_by')
              .order_by('-granted_at'))
    form = GrantCertificateForm()

    q = request.GET.get('q', '').strip()
    if q:
        grants = grants.filter(
            Q(user__username__icontains=q) | Q(certificate__name__icontains=q)
        )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'grant':
            form = GrantCertificateForm(request.POST)
            if form.is_valid():
                try:
                    uc = UserCertificate(
                        user=form.cleaned_data['user'],
                        certificate=form.cleaned_data['certificate'],
                        granted_by=request.user,
                        note=form.cleaned_data.get('note', ''),
                    )
                    uc.save()
                except IntegrityError:
                    messages.error(request, _('This certificate has already been granted to this user.'))
                    return redirect('accounts:admin_grant_certificate')
                audit(request, "ROLE_CHANGE",
                      f"Granted certificate '{uc.certificate.name}' to {uc.user.username}")
                messages.success(
                    request,
                    _('Certificate "%s" granted to %s.') % (uc.certificate.name, uc.user.username),
                )
                return redirect('accounts:admin_grant_certificate')

        elif action == 'revoke':
            pk = request.POST.get('grant_id')
            uc = get_object_or_404(UserCertificate, pk=pk)
            info = _('Certificate "%s" revoked from %s.') % (uc.certificate.name, uc.user.username)
            uc.delete()
            audit(request, "ROLE_CHANGE", str(info))
            messages.success(request, info)
            return redirect('accounts:admin_grant_certificate')

    paginator = Paginator(grants, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'accounts/admin_grant_certificate.html', {
        'grants': page_obj,
        'form': form,
        'q': q,
    })


__all__ = ['admin_certificates', 'admin_grant_certificate']
