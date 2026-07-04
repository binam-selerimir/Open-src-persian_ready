"""
posts/feeds.py
==============
RSS feed for the posts application.

Registered in posts/urls.py at the 'feed/' path and linked from base.html
via a <link rel="alternate"> autodiscovery tag.

LatestPostsFeed – the 20 most recently published visible posts.
"""

from django.contrib.syndication.views import Feed
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from .models import Post
from .utils import clean_post_body, looks_like_html


class LatestPostsFeed(Feed):
    """RSS 2.0 feed of the 20 most recent visible posts."""

    title = _('OpenSrc Persian — Latest Posts')
    description = _('Latest news and articles from OpenSrc Persian.')

    def link(self):
        """
        Return the canonical "view this on the site" URL for the feed.

        Must NOT be a bare class attribute like '/posts/': all posts URLs
        are wrapped in i18n_patterns(prefix_default_language=True), so the
        real URL is always /en/posts/ or /fa/posts/. reverse() adds the
        correct language prefix automatically (mirroring item_link(), which
        already relies on get_absolute_url() -> reverse()).
        """
        return reverse('posts:post_list')

    def items(self):
        return Post.objects.published().order_by('-pub_date')[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        """Return a safe plain-text excerpt for the RSS <description> tag.

        Uses summary first (author-written, trusted).  Falls back to a
        stripped+sanitised excerpt of the body to avoid serving raw HTML
        in the feed (which RSS readers render unsafely).
        """
        if item.summary:
            return strip_tags(item.summary)[:500]
        if item.body:
            body = item.body
            if looks_like_html(body):
                try:
                    body = clean_post_body(body)
                except ValidationError:
                    pass
            return strip_tags(body)[:500]
        return ''

    def item_pubdate(self, item):
        return item.pub_date

    def item_link(self, item):
        return item.get_absolute_url()
