"""
Regression and integration tests for the search app.

Run with:  python manage.py test search
"""

import re

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from posts.models import Category, Post, PostType


# ---------------------------------------------------------------------------
# LIKE wildcard escaping
# ---------------------------------------------------------------------------

class SearchLikeWildcardTests(TestCase):
    """Verify that search queries with LIKE wildcards work correctly."""

    def setUp(self):
        cat = Category.objects.create(name_en='Tech', name_fa='تکنولوژی', slug='tech')
        pt = PostType.objects.create(name_en='Article', slug='article')
        Post.objects.create(
            title='Price is 100 percent',
            slug='price-100-percent',
            category=cat, post_type=pt,
            body='<p>The price is 100 percent correct</p>',
            summary='price 100 percent',
            pub_date=timezone.now(), is_visible=True,
        )
        Post.objects.create(
            title='Score 95 percent',
            slug='score-95-percent',
            category=cat, post_type=pt,
            body='<p>Score is 95 percent</p>',
            summary='score 95 percent',
            pub_date=timezone.now(), is_visible=True,
        )
        self.url = reverse('search:search')

    def test_percent_in_query_matches_correctly(self):
        """Searching with % in query should return results matching the pattern."""
        resp = self.client.get(self.url, {'q': '100'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Price is 100 percent', html)
        # Score 95 percent must NOT appear in the search results (news-grid),
        # though it may appear elsewhere on the page (e.g. nav "Latest" menu).
        grid_match = re.search(r'<div class="news-grid">(.*?)</div>\s*</div>', html, re.DOTALL)
        grid_html = grid_match.group(1) if grid_match else ''
        self.assertNotIn('Score 95 percent', grid_html)


# ---------------------------------------------------------------------------
# q parameter truncation
# ---------------------------------------------------------------------------

class SearchQLengthTests(TestCase):
    """Verify that the q parameter is truncated to prevent slow-query DoS."""

    def setUp(self):
        self.url = reverse('search:search')

    def test_long_q_is_truncated(self):
        long_q = 'a' * 500
        resp = self.client.get(self.url, {'q': long_q})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Search rate limiting
# ---------------------------------------------------------------------------

class SearchRateLimitTests(TestCase):
    """Verify that the search endpoint has rate limiting."""

    def setUp(self):
        self.url = reverse('search:search')

    def test_search_returns_200_for_normal_requests(self):
        resp = self.client.get(self.url, {'q': 'test'})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Pagination links — duplicate ?page= query param (fixed)
# ---------------------------------------------------------------------------

class SearchPaginationTests(TestCase):
    """
    Before the fix, search.html built pagination links as
    "?{{ request.GET.urlencode }}&page=N", which appends a *second*
    page= parameter on top of whatever page= was already in the
    querystring -- e.g. "?q=test&page=1&page=2". QueryDict.get('page')
    still returns the last value so the link technically worked, but the
    querystring grew an extra page= on every click. The fix uses
    {% url_replace page=... %}, which replaces (not appends) the page
    parameter, like the other paginated templates in this project.
    """

    def setUp(self):
        cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        pt = PostType.objects.create(name_en='Article', slug='article')
        for i in range(25):
            Post.objects.create(
                title=f'Searchable post {i}',
                slug=f'searchable-post-{i}',
                category=cat,
                post_type=pt,
                body='<p>needle content</p>',
                summary='needle',
                pub_date=timezone.now(),
                is_visible=True,
            )
        self.url = reverse('search:search')

    def test_next_link_does_not_duplicate_page_param(self):
        resp = self.client.get(self.url, {'q': 'needle', 'page': '1'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        m = re.search(r'href="(\?[^"]*page=2[^"]*)"[^>]*>\s*Next', html)
        self.assertIsNotNone(m, "expected a 'Next' pagination link to page 2")
        next_href = m.group(1)

        # The querystring must contain exactly one page= parameter.
        self.assertEqual(next_href.count('page='), 1, next_href)

    def test_next_link_preserves_search_query_and_resolves(self):
        resp = self.client.get(self.url, {'q': 'needle', 'page': '1'})
        html = resp.content.decode('utf-8')

        m = re.search(r'href="(\?[^"]*page=2[^"]*)"[^>]*>\s*Next', html)
        next_href = m.group(1).replace('&amp;', '&')

        # The search keyword must be preserved across the pagination link.
        self.assertIn('q=needle', next_href)

        follow = self.client.get(self.url + next_href)
        self.assertEqual(follow.status_code, 200)
        follow_html = follow.content.decode('utf-8')
        # On page 2, the "Previous" link must point back to page 1 with a
        # single page= parameter too.
        m2 = re.search(r'href="(\?[^"]*page=1[^"]*)"[^>]*>\s*&laquo;', follow_html)
        self.assertIsNotNone(m2, "expected a 'Previous' pagination link to page 1")
        self.assertEqual(m2.group(1).count('page='), 1, m2.group(1))

    def test_repeated_pagination_does_not_accumulate_page_params(self):
        """Clicking 'Next' multiple times in a row must not grow the querystring."""
        href = '?q=needle&page=1'
        for _ in range(3):
            resp = self.client.get(self.url + href)
            html = resp.content.decode('utf-8')
            m = re.search(r'href="(\?[^"]*page=\d+[^"]*)"[^>]*>\s*Next', html)
            if not m:
                break
            href = m.group(1).replace('&amp;', '&')
            self.assertEqual(href.count('page='), 1, href)
