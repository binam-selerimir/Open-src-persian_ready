"""
posts/templatetags/post_extras.py
===================================
Custom Django template tags and filters for the posts app.

Tags
----
url_replace  – rebuild the current query string with selected keys replaced;
               preserves existing pagination/filter params when changing one value.

Filters
-------
render_post_body  – sanitise and render post body HTML or plain text safely.
type_label        – return a PostType's localised display name.
post_excerpt      – return a plain-text excerpt of N words from a post body.
table_of_contents – generate a <ul> TOC from h2/h3 headings in the post body.
"""

from django import template
from django.template.defaultfilters import linebreaks
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
import re

from posts.utils import clean_post_body, looks_like_html, slugify_heading


register = template.Library()

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

# Detects HTML entities that indicate the content was already escaped
# (e.g. by the Post.save() error fallback using django.utils.html.escape).
# If the body contains these entities, render_post_body applies linebreaks
# without re-escaping to prevent double-escaping like &amp;lt;.
_HTML_ENTITY_RE = re.compile(r'&(?:lt|gt|amp|quot|#39|#x27);')


@register.filter
def css_color(value):
    """
    Return the value if it is a valid 7-character hex color (#RRGGBB),
    otherwise return an empty string. Prevents CSS injection when accent
    colors are embedded in inline style attributes.
    """
    if not value:
        return ''
    s = str(value).strip()
    if _HEX_COLOR_RE.match(s):
        return s
    return ''


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Return the current query string with specific keys replaced or removed.

    Usage in a template:
        ?{% url_replace page=page_obj.next_page_number %}
        ?{% url_replace category="tech" page=None %}   {# removes page param #}

    Preserves all existing GET params (category, type, tag, …) and only
    overrides the keys you supply.  Passing None or '' removes the key entirely.

    This allows pagination links and filter toggles to work without losing
    each other's state.
    """
    query = context['request'].GET.copy()   # Mutable copy of the QueryDict.
    for key, value in kwargs.items():
        if value is None or value == '':
            query.pop(key, None)    # Remove the key if the new value is empty.
        else:
            query[key] = value      # Update or add the key.
    return query.urlencode()


@register.filter
def render_post_body(value):
    """
    Render a post body value safely in a template.

    If the value looks like HTML (contains a tag), it is passed through
    clean_post_body() for sanitisation (bleach + heading IDs + noopener)
    and marked as safe so Django doesn't double-escape it.

    If the value is plain text, it is escaped first (preventing XSS) then
    wrapped in <p> tags by Django's linebreaks filter.

    If the value contains HTML entities (e.g. &lt; &amp;), it was already
    escaped by the Post.save() error fallback — apply linebreaks without
    re-escaping to prevent double-escaping.

    Returns an empty string if value is falsy or if clean_post_body raises
    a ValidationError (body too long).
    """
    if not value:
        return ''

    try:
        if looks_like_html(value):
            return mark_safe(clean_post_body(value))
        # If the content contains HTML entities, it was pre-escaped
        # (e.g. Post.save() error fallback). Apply linebreaks without
        # re-escaping to avoid double-escaping like &amp;lt;.
        if _HTML_ENTITY_RE.search(value):
            return linebreaks(value)
        # Plain text: escape special characters, then convert newlines to <p> / <br>.
        return linebreaks(escape(value))
    except ValidationError:
        return ''


@register.filter
def type_label(post_type, language_code='en'):
    """
    Return the localised display name for a PostType object.

    Usage:   {{ post.post_type|type_label:LANGUAGE_CODE }}

    Falls back to the English name when the language is unsupported or the
    Persian name is not filled in.
    """
    if not post_type:
        return ''
    return post_type.label(language_code)


@register.filter
def post_excerpt(value, words=30):
    """
    Return the first N words of a post body as plain text.

    HTML tags are stripped before counting words so markup doesn't inflate
    or break the excerpt.  Adds an ellipsis (…) if the body was truncated.

    Usage:   {{ post.body|post_excerpt:50 }}
    """
    if not value:
        return ''

    # Validate that `words` is a usable integer; default to 30 if not.
    try:
        words = max(1, int(words))
    except (TypeError, ValueError):
        words = 30

    # Strip HTML tags for a clean plain-text excerpt.
    text = strip_tags(value) if looks_like_html(value) else value

    parts = text.split()

    if len(parts) <= words:
        return text     # Shorter than the limit — return as-is without ellipsis.

    return ' '.join(parts[:words]) + '…'


@register.filter
def table_of_contents(value):
    """
    Extract h2/h3 headings from an HTML post body and return a TOC <ul>.
    h4 headings are also scanned (but not listed) purely so the anchor
    numbering for duplicate heading text stays aligned with _add_heading_ids().

    Returns an empty string if the body has fewer than 2 h2/h3 headings (a
    single heading doesn't benefit from navigation).

    Anchor IDs are computed using the same slugify_heading() logic that
    _add_heading_ids() in posts/utils.py uses when sanitising the body, so
    TOC links always match the real heading IDs — including the '-1', '-2'
    suffixes applied to duplicate heading text.

    The returned HTML is marked safe; all heading text is escaped.
    """
    if not value:
        return ''

    # Scan h2/h3/h4 (same as _add_heading_ids' _HEADING_RE) so the `used`
    # dedup counts below stay in lock-step with the ids actually written
    # into the body -- even when an h4 shares slugified text with a later
    # h2/h3. Only h2/h3 are rendered as <li> entries; h4 doesn't appear in
    # the TOC but still consumes a slot in `used` if it comes first.
    all_headings = re.findall(r'<(h[234])[^>]*>(.*?)</\1>', value, re.IGNORECASE | re.DOTALL)

    # Don't render a TOC for posts with fewer than 2 h2/h3 headings -- a
    # single heading doesn't benefit from navigation.
    if sum(1 for tag, _inner in all_headings if tag.lower() in ('h2', 'h3')) < 2:
        return ''

    # Mirror the deduplication logic in _add_heading_ids so TOC anchors always
    # match the actual heading IDs (duplicate headings get "-1", "-2" suffixes).
    used: dict = {}
    items = []
    for tag, inner in all_headings:
        text = strip_tags(inner).strip()
        base_anchor = slugify_heading(text)
        count = used.get(base_anchor, 0)
        used[base_anchor] = count + 1
        if tag.lower() not in ('h2', 'h3'):
            continue
        # First occurrence uses the base slug; subsequent ones get a numeric suffix.
        anchor = base_anchor if count == 0 else f'{base_anchor}-{count}'
        # h3 headings get an indented style to show hierarchy.
        indent = ' class="toc-sub"' if tag.lower() == 'h3' else ''
        items.append(f'<li{indent}><a href="#{anchor}">{escape(text)}</a></li>')

    return mark_safe('<ul class="toc-list">' + ''.join(items) + '</ul>')


@register.filter(name='render_body_for_post', is_safe=True)
def render_body_for_post(post):
    from posts.utils.sanitization import render_markdown_body

    if post.body_md_file:
        try:
            post.body_md_file.open('rb')
            md_text = post.body_md_file.read()
            post.body_md_file.close()
            if isinstance(md_text, bytes):
                md_text = md_text.decode('utf-8', errors='replace')
            rendered = render_markdown_body(md_text)
        except Exception:
            rendered = render_post_body(post.body or '')
    else:
        rendered = render_post_body(post.body or '')

    return mark_safe(rendered)
