from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from ..forms import ProfileEditForm, UserEditForm
from ..models import UserProfile, UserCertificate
from posts.models import Post

User = get_user_model()


@login_required(login_url='accounts:login')
def panel_dashboard(request):
    return render(request, 'accounts/panel.html', {'active_tab': 'profile'})


@login_required(login_url='accounts:login')
def edit_profile(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    user_form = UserEditForm(request.POST or None, request.FILES or None, instance=request.user)
    profile_form = ProfileEditForm(request.POST or None, instance=profile)
    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user_form.save()
                profile_form.save()
            messages.success(request, _('Profile updated successfully.'))
            return redirect('accounts:panel')
        messages.error(request, _('Please correct the errors below.'))

    return render(request, 'accounts/edit_profile.html', {
        'user_form': user_form, 'profile_form': profile_form, 'active_tab': 'edit',
    })


def public_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    published_posts = Post.objects.published().filter(
        publisher=profile_user,
    ).select_related('category', 'post_type').prefetch_related('tags').only(
        'id', 'title', 'slug', 'pub_date', 'summary', 'cover_image',
        'category__id', 'category__name_en', 'category__slug',
        'post_type__id', 'post_type__name_en', 'post_type__accent_color',
    ).order_by('-pub_date')
    visible_certs = (UserCertificate.objects
                     .filter(user=profile_user, is_visible=True)
                     .select_related('certificate')
                     .order_by('-granted_at'))
    return render(request, 'accounts/public_profile.html', {
        'profile_user': profile_user, 'published_posts': published_posts,
        'visible_certs': visible_certs,
    })


@login_required(login_url='accounts:login')
def user_certificates(request):
    certs = (UserCertificate.objects
             .filter(user=request.user)
             .select_related('certificate', 'granted_by')
             .order_by('-granted_at'))
    return render(request, 'accounts/user_certificates.html', {'certs': certs})
