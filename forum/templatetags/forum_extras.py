import bleach
from django import template
from django.db.models import Count
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def forum_post_count(user):
    from forum.models import ForumPost
    if not user or not user.pk:
        return 0
    return ForumPost.objects.filter(author=user, is_deleted=False).count()


@register.filter
def forum_thread_count(board):
    return board.threads.filter(is_deleted=False).count()


_FORUM_BODY_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'a', 'ul', 'ol', 'li',
    'h2', 'h3', 'h4', 'blockquote', 'pre', 'code',
    'img', 'video', 'audio', 'source', 'div', 'figure', 'figcaption',
]
_FORUM_BODY_ATTRS = {
    'a': ['href', 'title', 'rel', 'target'],
    'code': ['class'], 'pre': ['class'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading', 'class'],
    'video': ['src', 'controls', 'preload', 'width', 'height', 'poster', 'class'],
    'audio': ['src', 'controls', 'preload', 'class'],
    'source': ['src', 'type'],
    'div': ['class'], 'figure': ['class'], 'figcaption': ['class'],
}
_FORUM_BODY_PROTOCOLS = ['http', 'https', 'mailto']


@register.filter
def render_forum_body(value):
    """Render-time sanitization for forum post bodies (defense-in-depth)."""
    if not value:
        return ''
    cleaned = bleach.clean(
        str(value),
        tags=_FORUM_BODY_TAGS,
        attributes=_FORUM_BODY_ATTRS,
        protocols=_FORUM_BODY_PROTOCOLS,
        strip=True,
    )
    return mark_safe(cleaned)
