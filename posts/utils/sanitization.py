import re
from posixpath import normpath
from pathlib import Path
import urllib.parse

import bleach
from django.core.exceptions import ValidationError

ALLOWED_BODY_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's',
    'a', 'ul', 'ol', 'li', 'h2', 'h3', 'h4',
    'blockquote', 'pre', 'code',
    'img', 'video', 'audio', 'source',
    'div', 'figure', 'figcaption',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'span', 'details', 'summary',  # admonitions + math (arithmatex)
]

ALLOWED_BODY_ATTRIBUTES = {
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
    'p': ['class'],          # admonition titles
    'span': ['class'],       # arithmatex math containers
    'details': ['open'],     # collapsible admonitions
    'summary': ['class'],    # summary element in details
}

INLINE_MEDIA_PREFIX = '/media/posts/inline/'
MAX_POST_BODY_LENGTH = 500_000

ALLOWED_INLINE_EXTENSIONS = {
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
    'audio': {'.mp3', '.ogg', '.wav', '.m4a', '.flac', '.aac'},
    'video': {'.mp4', '.webm', '.ogv', '.mov', '.m4v'},
}

HTML_TAG_RE = re.compile(r'<[a-z][\s\S]*?>', re.I)
MEDIA_TAG_RE = re.compile(
    r'<(img|video|audio|source)\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>',
    re.I,
)
VIDEO_POSTER_RE = re.compile(
    r'(<video\b[^>]*?)\bposter=["\']([^"\']+)["\']([^>]*>)',
    re.I,
)
HEADING_RE = re.compile(
    r'<(h[234])([^>]*)>(.*?)</\1>',
    re.IGNORECASE | re.DOTALL,
)
BLANK_LINK_RE = re.compile(
    r'''<a\b([^>]*?)\btarget\s*=\s*["']_blank["']([^>]*)>''',
    re.I,
)
_MEDIA_TAGS = {'img', 'video', 'audio', 'source'}


def slugify_heading(text):
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s]+', '-', slug)
    return slug.strip('-')


def looks_like_html(text):
    return bool(HTML_TAG_RE.search(text))


def _media_src_allowed(src):
    """Reject media src values that point outside the allowed upload directory.

    Security checks performed:
    1. Blocks absolute URLs, data: URIs, protocol-relative and javascript: URLs.
    2. Decodes up to 3 levels of URL-encoding to catch double/triple-encoded
       path traversal (e.g. %252e%252e%252f).
    3. Strips query strings and fragments before normalisation.
    4. Rejects any path containing /../ or starting with ..
    5. Validates file extension against ALLOWED_INLINE_EXTENSIONS.
    6. Must start with INLINE_MEDIA_PREFIX (must match posts/inline upload_to).
    """
    if not src:
        return False
    if src.startswith(('http://', 'https://', '//', 'data:', 'javascript:')):
        return False
    decoded = src
    for _ in range(3):  # decode up to 3 levels to catch double-encoded %2e%2e%2f
        new_decoded = urllib.parse.unquote(decoded)
        if new_decoded == decoded:
            break
        decoded = new_decoded
    clean = decoded.split('?')[0].split('#')[0]
    normalized = normpath(clean)
    if '/../' in normalized or normalized.startswith('..'):
        return False
    ext = Path(normalized).suffix.lower()
    allowed_exts = (
        ALLOWED_INLINE_EXTENSIONS['image']
        | ALLOWED_INLINE_EXTENSIONS['audio']
        | ALLOWED_INLINE_EXTENSIONS['video']
    )
    if ext not in allowed_exts:
        return False
    # ALLOWED_MEDIA_PREFIX must match the upload_to in posts/utils/media.py
    return normalized.startswith('/media/posts/')


def _body_attribute_filter(tag, name, value):
    allowed = ALLOWED_BODY_ATTRIBUTES.get(tag, [])
    if name not in allowed:
        return False
    if name in ('src', 'poster') and tag in _MEDIA_TAGS:
        if not _media_src_allowed(value):
            return False
    return True


def _strip_external_media(html):
    def _replace(match):
        return match.group(0) if _media_src_allowed(match.group(2)) else ''

    html = MEDIA_TAG_RE.sub(_replace, html)

    def _strip_poster(match):
        before, poster_url, after = match.group(1), match.group(2), match.group(3)
        if _media_src_allowed(poster_url):
            return f'{before}poster="{poster_url}"{after}'
        return f'{before}{after}'

    html = VIDEO_POSTER_RE.sub(_strip_poster, html)
    return html


def _add_heading_ids(html):
    def _make_slug(inner_html):
        text = re.sub(r'<[^>]+>', '', inner_html)
        return slugify_heading(text)

    used = {}

    def _replacer(match):
        tag, attrs, inner = match.group(1), match.group(2), match.group(3)
        if 'id=' in attrs:
            return match.group(0)
        base_slug = _make_slug(inner)
        if not base_slug:
            return match.group(0)
        count = used.get(base_slug, 0)
        used[base_slug] = count + 1
        heading_id = base_slug if count == 0 else f'{base_slug}-{count}'
        return f'<{tag}{attrs} id="{heading_id}">{inner}</{tag}>'

    return HEADING_RE.sub(_replacer, html)


def _enforce_noopener(html):
    def _fix(match):
        before, after = match.group(1), match.group(2)
        attrs = (before + after).strip()
        existing_rel = re.search(r'\brel=["\']([^"\']*)["\']', attrs)
        if existing_rel:
            existing_vals = set(existing_rel.group(1).split())
            existing_vals.update({'noopener', 'noreferrer'})
            new_rel = ' '.join(sorted(existing_vals))
            attrs = re.sub(r'\brel=["\'][^"\']*["\']', f'rel="{new_rel}"', attrs)
        else:
            attrs += ' rel="noopener noreferrer"'
        return f'<a {attrs} target="_blank">'

    return BLANK_LINK_RE.sub(_fix, html)


def _enforce_attribute_filter(html):
    cleaner = bleach.Cleaner(
        tags=ALLOWED_BODY_TAGS,
        attributes=_body_attribute_filter,
        protocols=['http', 'https', 'mailto'],
        strip=True,
    )
    return cleaner.clean(html)


def clean_post_body(html):
    if not html:
        return ''
    if len(html) > MAX_POST_BODY_LENGTH:
        raise ValidationError(f'Post body exceeds {MAX_POST_BODY_LENGTH:,} characters.')
    if not looks_like_html(html):
        return html

    cleaned = bleach.clean(
        html, tags=ALLOWED_BODY_TAGS, attributes=ALLOWED_BODY_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'], strip=True, css_sanitizer=None,
    )
    cleaned = _enforce_attribute_filter(cleaned)
    cleaned = _add_heading_ids(cleaned)
    cleaned = _strip_external_media(cleaned)
    cleaned = _enforce_noopener(cleaned)
    return cleaned


def render_markdown_body(md_text):
    """Render markdown to sanitized HTML.

    Extensions:
    - fenced_code: fenced code blocks (```)
    - tables: markdown tables
    - admonition: !!! warning / !!! note blocks
    - pymdownx.arithmatex: LaTeX math ($...$, $$...$$, \(...\), \[...\])
    - pymdownx.highlight: syntax highlighting for code blocks
    - pymdownx.superfences: enhanced fenced code blocks
    """
    import markdown as _markdown
    raw_html = _markdown.markdown(
        md_text,
        extensions=[
            'fenced_code',
            'tables',
            'admonition',
            'pymdownx.arithmatex',
            'pymdownx.highlight',
            'pymdownx.superfences',
        ],
        extension_configs={
            'pymdownx.arithmatex': {
                'generic': True,  # outputs \(...\) in <span>, NOT <script>
                'inline_syntax': ['dollar', 'round'],
                'block_syntax': ['dollar', 'square', 'begin'],
            },
            'pymdownx.highlight': {
                'css_class': 'highlight',
            },
        },
    )
    return clean_post_body(raw_html)
