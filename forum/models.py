import bleach
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from posts.utils.sanitization import (
    ALLOWED_BODY_ATTRIBUTES,
    ALLOWED_BODY_TAGS,
    clean_post_body,
)

FORUM_SANITIZE_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'a', 'ul', 'ol', 'li',
    'blockquote', 'pre', 'code',
    'img', 'video', 'audio', 'source', 'div', 'figure', 'figcaption',
]

FORUM_SANITIZE_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
    'code': ['class'],
    'pre': ['class'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading', 'class'],
    'video': ['src', 'controls', 'preload', 'width', 'height', 'poster', 'class'],
    'audio': ['src', 'controls', 'preload', 'class'],
    'source': ['src', 'type'],
    'div': ['class'],
    'figure': ['class'],
    'figcaption': ['class'],
}

MAX_FORUM_BODY_LENGTH = 500000


def _sanitize_forum_body(body):
    if len(body) > MAX_FORUM_BODY_LENGTH:
        from django.core.exceptions import ValidationError
        raise ValidationError('Post body too long.')
    try:
        return clean_post_body(body)
    except ValidationError:
        raise
    except Exception:
        return bleach.clean(
            body,
            tags=FORUM_SANITIZE_TAGS,
            attributes=FORUM_SANITIZE_ATTRIBUTES,
            protocols=['http', 'https', 'mailto'],
            strip=True,
        )


class Board(models.Model):
    name_en = models.CharField(_('Name (EN)'), max_length=120)
    name_fa = models.CharField(_('Name (FA)'), max_length=120, blank=True)
    slug = models.SlugField(_('Slug'), max_length=120, unique=True, allow_unicode=True)
    description_en = models.TextField(_('Description (EN)'), blank=True)
    description_fa = models.TextField(_('Description (FA)'), blank=True)
    order = models.PositiveSmallIntegerField(_('Order'), default=0)
    is_active = models.BooleanField(_('Active'), default=True)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        ordering = ['order', 'name_en']
        verbose_name = _('Board')
        verbose_name_plural = _('Boards')

    def __str__(self):
        return self.name_en

    def get_absolute_url(self):
        return reverse('forum:board_detail', kwargs={'board_slug': self.slug})

    @property
    def thread_count(self):
        # PERFORMANCE: fires a query per board when accessed in a list.
        return self.threads.filter(is_deleted=False).count()

    @property
    def post_count(self):
        # PERFORMANCE: fires a query per board when accessed in a list.
        return ForumPost.objects.filter(
            thread__board=self, is_deleted=False, thread__is_deleted=False
        ).count()

    @property
    def last_post(self):
        # PERFORMANCE: fires a query per board when accessed in a list.
        return (
            ForumPost.objects.filter(
                thread__board=self, is_deleted=False, thread__is_deleted=False,
            )
            .select_related('author', 'thread')
            .order_by('-created_at')
            .first()
        )


class Thread(models.Model):
    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name='threads',
        verbose_name=_('Board'),
    )
    title = models.CharField(_('Title'), max_length=255)
    slug = models.SlugField(
        _('Slug'), max_length=255, unique=True, allow_unicode=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='forum_threads',
        verbose_name=_('Author'),
    )
    is_sticky = models.BooleanField(_('Sticky'), default=False)
    is_closed = models.BooleanField(_('Closed'), default=False)
    is_deleted = models.BooleanField(_('Deleted'), default=False)
    view_count = models.PositiveIntegerField(
        _('View count'), default=0, editable=False,
    )
    reply_count = models.PositiveIntegerField(
        _('Reply count'), default=0, editable=False,
    )
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated'), auto_now=True)

    class Meta:
        ordering = ['-is_sticky', '-updated_at']
        indexes = [
            models.Index(
                fields=['board', 'is_deleted', '-updated_at'],
                name='thread_board_active_idx',
            ),
        ]
        verbose_name = _('Thread')
        verbose_name_plural = _('Threads')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('forum:thread_detail', kwargs={
            'board_slug': self.board.slug,
            'slug': self.slug,
        })

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)
            if not base_slug:
                base_slug = f'thread-{self.pk or ""}'
            slug = base_slug
            counter = 1
            while Thread.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ForumPost(models.Model):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name='posts',
        verbose_name=_('Thread'),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='forum_posts',
        verbose_name=_('Author'),
    )
    body = models.TextField(_('Body'))
    is_first_post = models.BooleanField(_('First post'), default=False)
    is_deleted = models.BooleanField(_('Deleted'), default=False)
    ip_address = models.GenericIPAddressField(
        _('IP address'), null=True, blank=True,
    )
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated'), auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['thread', 'is_deleted', 'created_at'],
                name='forumpost_thread_active_idx',
            ),
        ]
        verbose_name = _('Forum Post')
        verbose_name_plural = _('Forum Posts')

    def __str__(self):
        return f'Post #{self.pk} in \'{self.thread}\''

    def save(self, *args, **kwargs):
        self.body = _sanitize_forum_body(self.body)
        super().save(*args, **kwargs)
        Thread.objects.filter(pk=self.thread_id).update(
            reply_count=ForumPost.objects.filter(
                thread_id=self.thread_id, is_deleted=False, is_first_post=False,
            ).count(),
            updated_at=timezone.now(),
        )
