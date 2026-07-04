from django.db.models import F

from .sanitization import (
    clean_post_body, looks_like_html, slugify_heading,
    ALLOWED_BODY_TAGS, ALLOWED_BODY_ATTRIBUTES, INLINE_MEDIA_PREFIX,
    MAX_POST_BODY_LENGTH, ALLOWED_INLINE_EXTENSIONS,
    _add_heading_ids, _enforce_noopener, _media_src_allowed,
)
from .media import (
    detect_mime, classify_upload_file, validate_inline_upload, save_inline_media,
    MAX_INLINE_MEDIA_BYTES, ALLOWED_MIME_TYPES,
)


def increment_view_count(post):
    """Atomic increment of post view count using F() expression."""
    from posts.models import Post
    Post.objects.filter(pk=post.pk).update(view_count=F('view_count') + 1)


def increment_unique_view_count(post):
    """Atomic increment of post unique view count using F() expression."""
    from posts.models import Post
    Post.objects.filter(pk=post.pk).update(unique_view_count=F('unique_view_count') + 1)


__all__ = [
    # Sanitization
    'clean_post_body', 'looks_like_html', 'slugify_heading',
    'ALLOWED_BODY_TAGS', 'ALLOWED_BODY_ATTRIBUTES', 'INLINE_MEDIA_PREFIX',
    'MAX_POST_BODY_LENGTH', 'ALLOWED_INLINE_EXTENSIONS',
    # Internal helpers (imported by tests and template tags)
    '_add_heading_ids', '_enforce_noopener', '_media_src_allowed',
    # Media upload
    'detect_mime', 'classify_upload_file', 'validate_inline_upload', 'save_inline_media',
    'MAX_INLINE_MEDIA_BYTES', 'ALLOWED_MIME_TYPES',
    # View counters
    'increment_view_count', 'increment_unique_view_count',
]
