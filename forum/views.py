from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from accounts.utils import audit, check_rate_limit, get_client_ip
from posts.utils.media import classify_upload_file, save_inline_media

from .forms import NewBoardForm, NewThreadForm, ReplyForm
from .models import Board, ForumPost, Thread

# ---------------------------------------------------------------------------
# Pagination & rate-limit constants — kept here so tuning is one-line.
# ---------------------------------------------------------------------------
THREADS_PER_PAGE = 30
POSTS_PER_PAGE = 20

# (count, ttl_seconds) — checked by check_rate_limit().
FORUM_NEW_THREAD_RATE_LIMIT = (3, 600)     # 3 threads per 10 min
FORUM_REPLY_RATE_LIMIT = (5, 300)          # 5 replies per 5 min
FORUM_UPLOAD_RATE_LIMIT = (10, 300)        # 10 uploads per 5 min


def forum_index(request):
    boards = Board.objects.filter(is_active=True).order_by('order', 'name_en')
    board_data = []
    for board in boards:
        board_data.append({
            'board': board,
            'thread_count': board.thread_count,
            'post_count': board.post_count,
            'last_post': board.last_post,
        })
    return render(request, 'forum/index.html', {
        'board_data': board_data,
        'page_title': 'Forum',
    })


@login_required(login_url='accounts:login')
def new_board(request):
    if not request.user.is_site_admin:
        return HttpResponseForbidden(_('Admin access required.'))
    form = NewBoardForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        board = form.save()
        audit(request, 'POST_CREATE', f'Forum board created: {board.name_en}')
        messages.success(request, _('Board created successfully.'))
        return redirect(board)
    return render(request, 'forum/new_board.html', {
        'form': form,
    })


def board_detail(request, board_slug):
    board = get_object_or_404(Board, slug=board_slug, is_active=True)
    threads = (
        Thread.objects
        .filter(board=board, is_deleted=False)
        .select_related('author')
        .order_by('-is_sticky', '-updated_at')
    )
    paginator = Paginator(threads, THREADS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'forum/board_detail.html', {
        'board': board,
        'threads': page_obj,
        'page_obj': page_obj,
    })


def thread_detail(request, board_slug, slug):
    board = get_object_or_404(Board, slug=board_slug, is_active=True)
    thread = get_object_or_404(
        Thread, slug=slug, board=board, is_deleted=False,
    )
    Thread.objects.filter(pk=thread.pk).update(view_count=F('view_count') + 1)
    thread.refresh_from_db()

    posts = (
        ForumPost.objects
        .filter(thread=thread, is_deleted=False)
        .select_related('author', 'author__profile')
        .order_by('created_at')
    )
    paginator = Paginator(posts, POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    reply_form = None
    if not thread.is_closed and request.user.is_authenticated:
        reply_form = ReplyForm()

    return render(request, 'forum/thread_detail.html', {
        'thread': thread,
        'board': board,
        'posts': page_obj,
        'page_obj': page_obj,
        'reply_form': reply_form,
    })


@login_required(login_url='accounts:login')
def new_thread(request, board_slug):
    board = get_object_or_404(Board, slug=board_slug, is_active=True)
    ip = get_client_ip(request)

    if not check_rate_limit(request, 'forum_new_thread', *FORUM_NEW_THREAD_RATE_LIMIT):
        messages.error(request, _('You are creating threads too quickly. Please wait.'))
        return redirect(board)

    form = NewThreadForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        title = form.cleaned_data['title']
        body = form.cleaned_data['body']
        with transaction.atomic():
            thread = Thread.objects.create(
                board=board,
                title=title,
                author=request.user,
            )
            ForumPost.objects.create(
                thread=thread,
                author=request.user,
                body=body,
                is_first_post=True,
                ip_address=ip,
            )
        audit(request, 'POST_CREATE', f'Forum thread created: {thread.title}')
        messages.success(request, _('Thread created successfully.'))
        return redirect(thread)
    return render(request, 'forum/new_thread.html', {
        'board': board,
        'form': form,
    })


@login_required(login_url='accounts:login')
def reply(request, pk):
    thread = get_object_or_404(Thread, pk=pk, is_deleted=False)

    if thread.is_closed:
        messages.error(request, _('This thread is closed.'))
        return HttpResponseForbidden(_('Thread is closed.'))

    ip = get_client_ip(request)
    if not check_rate_limit(request, 'forum_reply', *FORUM_REPLY_RATE_LIMIT):
        messages.error(request, _('You are replying too quickly. Please wait.'))
        return redirect(thread)

    form = ReplyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        body = form.cleaned_data['body']
        ForumPost.objects.create(
            thread=thread,
            author=request.user,
            body=body,
            ip_address=ip,
        )
        audit(request, 'POST_CREATE', f'Forum reply in: {thread.title}')
        messages.success(request, _('Reply posted.'))
        last_page = thread.posts.filter(is_deleted=False).count()
        page_num = (last_page - 1) // POSTS_PER_PAGE + 1
        return redirect(f'{thread.get_absolute_url()}?page={page_num}')
    return redirect(thread)


@login_required(login_url='accounts:login')
def edit_post(request, pk):
    post = get_object_or_404(
        ForumPost, pk=pk, is_deleted=False, thread__is_deleted=False,
    )
    if post.author != request.user and not request.user.is_site_admin:
        return HttpResponseForbidden(_('You cannot edit this post.'))

    form = ReplyForm(request.POST or None, initial={'body': post.body})
    if request.method == 'POST' and form.is_valid():
        post.body = form.cleaned_data['body']
        post.save()
        audit(request, 'POST_EDIT', f'Forum post #{post.pk} edited in: {post.thread.title}')
        messages.success(request, _('Post updated.'))
        return redirect(post.thread)
    return render(request, 'forum/edit_post.html', {
        'post': post,
        'thread': post.thread,
        'form': form,
    })


@login_required(login_url='accounts:login')
def delete_post(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest(_('POST required.'))
    post = get_object_or_404(ForumPost, pk=pk, is_deleted=False, thread__is_deleted=False)
    if post.author != request.user and not request.user.is_site_admin:
        return HttpResponseForbidden(_('You cannot delete this post.'))
    if post.is_first_post:
        messages.error(request, _('Cannot delete the first post of a thread.'))
        return HttpResponseBadRequest(_('Cannot delete first post.'))
    post.is_deleted = True
    post.save()
    audit(request, 'POST_DELETE', f'Forum post #{post.pk} deleted in: {post.thread.title}')
    messages.success(request, _('Post deleted.'))
    return redirect(post.thread)


@login_required(login_url='accounts:login')
def delete_thread(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest(_('POST required.'))
    if not request.user.is_site_admin:
        return HttpResponseForbidden(_('Admin access required.'))
    thread = get_object_or_404(Thread, pk=pk, is_deleted=False)
    thread.is_deleted = True
    thread.save()
    audit(request, 'POST_DELETE', f'Forum thread deleted: {thread.title}')
    messages.success(request, _('Thread deleted.'))
    return redirect(thread.board)


@login_required(login_url='accounts:login')
def toggle_sticky(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest(_('POST required.'))
    if not request.user.is_site_admin:
        return HttpResponseForbidden(_('Admin access required.'))
    thread = get_object_or_404(Thread, pk=pk, is_deleted=False)
    Thread.objects.filter(pk=pk).update(is_sticky=~F('is_sticky'))
    thread.refresh_from_db()
    state = "pinned" if thread.is_sticky else "unpinned"
    audit(request, 'POST_EDIT', f'Forum thread {state}: {thread.title}')
    return redirect(thread)


@login_required(login_url='accounts:login')
def toggle_close(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest(_('POST required.'))
    if not request.user.is_site_admin:
        return HttpResponseForbidden(_('Admin access required.'))
    thread = get_object_or_404(Thread, pk=pk, is_deleted=False)
    Thread.objects.filter(pk=pk).update(is_closed=~F('is_closed'))
    thread.refresh_from_db()
    state = "closed" if thread.is_closed else "opened"
    audit(request, 'POST_EDIT', f'Forum thread {state}: {thread.title}')
    return redirect(thread)


@login_required(login_url='accounts:login')
def upload_forum_media(request):
    if request.method != 'POST':
        return JsonResponse({'error': _('POST required.')}, status=405)
    if not check_rate_limit(request, 'forum_upload_media', *FORUM_UPLOAD_RATE_LIMIT):
        return JsonResponse({'error': _('Upload limit reached. Please wait.')}, status=429)
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': _('No file provided.')}, status=400)
    url, error = save_inline_media(uploaded)
    if error:
        return JsonResponse({'error': error}, status=400)
    file_type = classify_upload_file(uploaded.name) or 'unknown'
    audit(request, 'POST_CREATE', f'Forum media uploaded: {uploaded.name}')
    return JsonResponse({'url': url, 'type': file_type, 'name': uploaded.name})
