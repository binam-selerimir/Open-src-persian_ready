import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_COMMENT_TAGS = ['p', 'br', 'strong', 'em', 'a']
ALLOWED_COMMENT_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
}


@register.filter
def render_comment_body(value):
    """
    Sanitize and render a comment body at render time as defense-in-depth.

    The comment body is already sanitized at form validation time via
    bleach.clean() in CommentForm.clean_body(). This filter applies the
    same sanitization again at render time to guard against:
    - Comments created via Django admin, shell, or data migrations
      that bypass the form validation.
    - Any future code path that creates comments without going through
      the CommentForm.

    This is defense-in-depth: storage-time sanitization is the primary
    control; render-time sanitization is the safety net.
    """
    if not value:
        return ''
    cleaned = bleach.clean(
        value,
        tags=ALLOWED_COMMENT_TAGS,
        attributes=ALLOWED_COMMENT_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        strip=True,
    )
    return mark_safe(cleaned)
