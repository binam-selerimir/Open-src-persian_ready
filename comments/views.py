from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _

from posts.models import Post

from accounts.utils import check_rate_limit, get_client_ip

from .forms import CommentForm
from .models import Comment


@login_required(login_url='accounts:login')
def add_comment(request, slug):
    """
    POST-only: create a comment for a post.

    Requires login. Rate-limited to 5 comments per IP per 5 minutes.
    Comments are created with is_approved=False (require admin approval).
    author_name and author_email are set from the logged-in user's account.
    """
    post = get_object_or_404(Post.objects.published(), slug=slug)

    if request.method != 'POST':
        messages.error(request, _('Only POST requests are allowed.'))
        return redirect(post.get_absolute_url())

    if not check_rate_limit(request, 'comment', limit=5, ttl=300):
        messages.error(request, _('Too many comments. Please wait before posting again.'))
        return redirect(post.get_absolute_url())

    form = CommentForm(request.POST)
    if form.is_valid():
        user = request.user
        author_name = user.get_full_name_display() or user.username
        author_email = user.email
        Comment.objects.create(
            post=post,
            author_name=author_name,
            author_email=author_email,
            body=form.cleaned_data['body'],
            ip_address=get_client_ip(request),
        )
        messages.success(request, _('Comment submitted. It will appear after admin approval.'))
    else:
        messages.error(request, _('Please correct the errors in your comment.'))

    return redirect(post.get_absolute_url())
