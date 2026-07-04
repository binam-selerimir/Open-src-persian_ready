"""
Regression and integration tests for the posts app.

Run with:  python manage.py test posts
"""

import re
from datetime import timedelta
from io import StringIO
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Post, PostType, Subcategory
from .templatetags.post_extras import table_of_contents

User = get_user_model()


# ---------------------------------------------------------------------------
# subcategories_json — ?category= integer-coercion bug (🔴 fixed)
# ---------------------------------------------------------------------------

class SubcategoriesJsonTests(TestCase):
    """
    Before the fix, a non-integer ?category= value caused Django's ORM to
    raise ValueError -> HTTP 500.  These tests pin the correct behaviour
    (graceful empty-list response) for every edge-case input.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@example.com'
        )
        self.client.force_login(self.user)
        self.cat = Category.objects.create(
            name_en='Technology', name_fa='فناوری', slug='technology'
        )
        Subcategory.objects.create(
            category=self.cat, name_en='Python', name_fa='پایتون', slug='python'
        )
        self.url = reverse('posts:subcategories_json')

    # ── happy path ────────────────────────────────────────────────────────────

    def test_valid_integer_id_returns_subcategories(self):
        resp = self.client.get(self.url, {'category': str(self.cat.pk)})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['slug'], 'python')

    def test_slug_lookup_returns_subcategories(self):
        resp = self.client.get(self.url, {'category_slug': 'technology'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_no_params_returns_empty_list(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_nonexistent_id_returns_empty_list(self):
        resp = self.client.get(self.url, {'category': '99999'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    # ── regression: non-integer values must NOT cause HTTP 500 ───────────────

    def test_alphabetic_category_returns_400_not_500(self):
        resp = self.client.get(self.url, {'category': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_empty_string_category_returns_empty_not_500(self):
        resp = self.client.get(self.url, {'category': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_float_string_category_returns_400_not_500(self):
        resp = self.client.get(self.url, {'category': '1.5'})
        self.assertEqual(resp.status_code, 400)

    def test_sql_injection_attempt_returns_400_not_500(self):
        resp = self.client.get(self.url, {'category': "1 OR 1=1"})
        self.assertEqual(resp.status_code, 400)

    # ── response structure ────────────────────────────────────────────────────

    def test_response_contains_expected_keys(self):
        resp = self.client.get(self.url, {'category': str(self.cat.pk)})
        item = resp.json()[0]
        self.assertIn('id', item)
        self.assertIn('name_en', item)
        self.assertIn('name_fa', item)
        self.assertIn('slug', item)

    def test_endpoint_requires_login(self):
        """Unauthenticated requests must be redirected to login."""
        self.client.logout()
        resp = self.client.get(self.url, {'category': str(self.cat.pk)})
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# LatestPostsFeed.link — hardcoded '/posts/' missing i18n prefix (fixed)
# ---------------------------------------------------------------------------

class LatestPostsFeedTests(TestCase):
    """
    Before the fix, LatestPostsFeed.link was the bare string '/posts/'.
    Every posts URL lives inside i18n_patterns(prefix_default_language=True),
    so '/posts/' 404s -- the feed's <link> element pointed at a dead URL.
    link() must now resolve to /en/posts/ (or /fa/posts/) via reverse().
    """

    def setUp(self):
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        Post.objects.create(
            title='Hello', slug='hello', category=self.cat, post_type=self.pt,
            body='<p>Hello world</p>', pub_date=timezone.now(), is_visible=True,
        )

    def test_feed_link_has_language_prefix_and_resolves(self):
        resp = self.client.get(reverse('posts:post_feed'))
        self.assertEqual(resp.status_code, 200)
        xml = resp.content.decode('utf-8')

        m = re.search(r'<link>([^<]+)</link>', xml)
        self.assertIsNotNone(m, "feed must contain a <link> element")
        link = m.group(1)

        # Django's syndication framework runs link() through add_domain(),
        # which prepends the absolute site domain (RSS requires absolute
        # URLs) -- e.g. 'http://testserver/en/posts/', not '/en/posts/'.
        # Check the PATH component, not the full URL string.
        path = urlparse(link).path
        self.assertNotEqual(path, '/posts/')
        self.assertTrue(
            path.startswith('/en/posts/') or path.startswith('/fa/posts/'),
            f"feed <link> path must include the i18n language prefix, got {path!r} (full link: {link!r})",
        )

        # The link must actually resolve (not 404) when followed.
        follow = self.client.get(path)
        self.assertEqual(follow.status_code, 200)

    def test_feed_item_link_also_has_language_prefix(self):
        resp = self.client.get(reverse('posts:post_feed'))
        xml = resp.content.decode('utf-8')
        item_link = re.search(r'<item>.*?<link>([^<]+)</link>', xml, re.DOTALL).group(1)
        item_path = urlparse(item_link).path
        self.assertTrue(item_path.startswith('/en/posts/') or item_path.startswith('/fa/posts/'))


# ---------------------------------------------------------------------------
# table_of_contents — h2/h3/h4 anchor-id dedup mismatch (fixed)
# ---------------------------------------------------------------------------

class TableOfContentsTests(TestCase):
    """
    _add_heading_ids (posts/utils.py) assigns ids across h2/h3/h4 headings,
    in document order, using a single shared "used slug" counter.
    table_of_contents() used to only scan h2/h3, so an h4 sharing slugified
    text with a later h2/h3 caused the TOC anchor to point at the wrong
    element's id. table_of_contents() must now scan h2/h3/h4 for the dedup
    count (while still only listing h2/h3 in the rendered <ul>).
    """

    def test_toc_anchors_match_heading_ids_with_interleaved_h4(self):
        body = (
            "<h2>Setup</h2><p>...</p>"
            "<h4>Setup</h4><p>...</p>"
            "<h3>Setup</h3><p>...</p>"
        )
        from .utils import _add_heading_ids
        ided = _add_heading_ids(body)
        ids = re.findall(r'<h[234] id="([^"]+)"', ided)
        self.assertEqual(len(ids), 3)

        toc = table_of_contents(body)
        hrefs = re.findall(r'href="#([^"]+)"', toc)
        # Only h2/h3 are listed (2 entries), and each href must match that
        # heading's *actual* id (ids[0]=h2, ids[1]=h4, ids[2]=h3).
        self.assertEqual(hrefs, [ids[0], ids[2]])
        self.assertNotEqual(hrefs[1], ids[1], "TOC must not point at the h4's id")

    def test_toc_skipped_for_fewer_than_two_headings(self):
        self.assertEqual(table_of_contents('<h2>Only one</h2><p>text</p>'), '')

    def test_toc_lists_h3_with_sub_class(self):
        body = '<h2>Intro</h2><p>x</p><h3>Details</h3><p>y</p>'
        toc = table_of_contents(body)
        self.assertIn('class="toc-sub"', toc)
        self.assertEqual(toc.count('<li'), 2)


# ---------------------------------------------------------------------------
# table_of_contents / _add_heading_ids — duplicate same-level headings (fixed,
# pre-existing behaviour preserved by the bug-8 fix)
# ---------------------------------------------------------------------------

class TableOfContentsDuplicateHeadingsTests(TestCase):

    def test_duplicate_h2_headings_get_unique_anchors(self):
        body = '<h2>Overview</h2><p>a</p><h2>Overview</h2><p>b</p>'
        from .utils import _add_heading_ids
        ided = _add_heading_ids(body)
        ids = re.findall(r'<h2 id="([^"]+)"', ided)
        self.assertEqual(ids, ['overview', 'overview-1'])

        toc = table_of_contents(body)
        hrefs = re.findall(r'href="#([^"]+)"', toc)
        self.assertEqual(hrefs, ids)


# ---------------------------------------------------------------------------
# seed_posts management command — missing PostType prerequisite (fixed)
# ---------------------------------------------------------------------------

class SeedPostsCommandTests(TestCase):
    """
    Before the fix, seed_posts called PostType.objects.get(slug=s) for
    'translation' / 'original_en' / 'original_fa', which raised
    PostType.DoesNotExist on a fresh database -- the command had a hidden
    prerequisite (create these three PostType rows via the admin first)
    that wasn't enforced or automated anywhere. get_or_create now creates
    them automatically, so the command works standalone on a fresh DB.
    """

    def test_runs_on_a_completely_fresh_database(self):
        # No PostType, Category, Tag, or Post rows exist yet -- this used
        # to crash with PostType.DoesNotExist before the fix.
        call_command('seed_posts', stdout=StringIO())

    def test_creates_the_three_expected_post_types(self):
        call_command('seed_posts', stdout=StringIO())
        slugs = set(PostType.objects.values_list('slug', flat=True))
        self.assertEqual(slugs, {'translation', 'original_en', 'original_fa'})

    def test_post_type_accent_colors_pass_model_validation(self):
        call_command('seed_posts', stdout=StringIO())
        for pt in PostType.objects.all():
            pt.full_clean()  # raises ValidationError if accent_color is malformed

    def test_reuses_existing_post_types_without_overwriting_them(self):
        # Simulate a user who already created their own PostType rows
        # (e.g. via the admin) with these exact slugs but different names.
        PostType.objects.create(slug='translation', name_en='Custom Name',
                                 accent_color='#000000')
        call_command('seed_posts', stdout=StringIO())
        pt = PostType.objects.get(slug='translation')
        self.assertEqual(pt.name_en, 'Custom Name')
        self.assertEqual(pt.accent_color, '#000000')

    def test_running_twice_does_not_duplicate_post_types(self):
        call_command('seed_posts', stdout=StringIO())
        call_command('seed_posts', stdout=StringIO())
        self.assertEqual(PostType.objects.count(), 3)

    def test_creates_fifteen_posts_on_first_run(self):
        call_command('seed_posts', stdout=StringIO())
        self.assertEqual(Post.objects.count(), 15)


# ===========================================================================
# NEW COMPREHENSIVE TESTS
# ===========================================================================


# ---------------------------------------------------------------------------
# Post model tests
# ---------------------------------------------------------------------------

class PostModelTests(TestCase):

    def setUp(self):
        self.cat = Category.objects.create(name_en='Tech', name_fa='تکنولوژی', slug='tech')
        self.pt = PostType.objects.create(name_en='Article', slug='article')

    def test_post_str(self):
        post = Post.objects.create(
            title='My Post', slug='my-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )
        self.assertEqual(str(post), 'My Post')

    def test_post_get_absolute_url(self):
        post = Post.objects.create(
            title='URL Test', slug='url-test', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )
        url = post.get_absolute_url()
        self.assertIn('/en/posts/url-test/', url)

    def test_post_slug_unique(self):
        Post.objects.create(
            title='First', slug='dup', category=self.cat, post_type=self.pt,
            body='<p>A</p>', pub_date=timezone.now(), is_visible=True,
        )
        with self.assertRaises(Exception):
            Post.objects.create(
                title='Second', slug='dup', category=self.cat, post_type=self.pt,
                body='<p>B</p>', pub_date=timezone.now(), is_visible=True,
            )

    def test_post_default_ordering(self):
        now = timezone.now()
        p1 = Post.objects.create(
            title='Old', slug='old', category=self.cat, post_type=self.pt,
            body='<p>O</p>', pub_date=now - timedelta(days=1), is_visible=True,
        )
        p2 = Post.objects.create(
            title='New', slug='new', category=self.cat, post_type=self.pt,
            body='<p>N</p>', pub_date=now, is_visible=True,
        )
        posts = list(Post.objects.all())
        self.assertEqual(posts[0].pk, p2.pk)


# ---------------------------------------------------------------------------
# Category model tests
# ---------------------------------------------------------------------------

class CategoryModelTests(TestCase):

    def test_category_str_en(self):
        cat = Category.objects.create(name_en='Tech', name_fa='تکنولوژی', slug='tech')
        self.assertEqual(str(cat), 'Tech')

    def test_category_slug_unique(self):
        Category.objects.create(name_en='A', name_fa='آ', slug='dup')
        with self.assertRaises(Exception):
            Category.objects.create(name_en='B', name_fa='ب', slug='dup')

    def test_category_ordering(self):
        Category.objects.create(name_en='B', name_fa='ب', slug='b', order=2)
        Category.objects.create(name_en='A', name_fa='آ', slug='a', order=1)
        cats = list(Category.objects.all())
        self.assertEqual(cats[0].name_en, 'A')


# ---------------------------------------------------------------------------
# Subcategory model tests
# ---------------------------------------------------------------------------

class SubcategoryModelTests(TestCase):

    def setUp(self):
        self.cat = Category.objects.create(name_en='Tech', name_fa='تکنولوژی', slug='tech')

    def test_subcategory_str(self):
        sub = Subcategory.objects.create(
            category=self.cat, name_en='Python', name_fa='پایتون', slug='python'
        )
        self.assertEqual(str(sub), 'Tech / Python')

    def test_subcategory_unique_together(self):
        Subcategory.objects.create(
            category=self.cat, name_en='A', name_fa='آ', slug='a'
        )
        with self.assertRaises(Exception):
            Subcategory.objects.create(
                category=self.cat, name_en='B', name_fa='ب', slug='a'
            )

    def test_same_slug_different_category_allowed(self):
        cat2 = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        Subcategory.objects.create(
            category=self.cat, name_en='Python', name_fa='پایتون', slug='python'
        )
        sub2 = Subcategory.objects.create(
            category=cat2, name_en='Python', name_fa='پایتون', slug='python'
        )
        self.assertIsNotNone(sub2.pk)


# ---------------------------------------------------------------------------
# PostType model tests
# ---------------------------------------------------------------------------

class PostTypeModelTests(TestCase):

    def test_posttype_str(self):
        pt = PostType.objects.create(name_en='Article', slug='article')
        self.assertEqual(str(pt), 'Article')

    def test_posttype_accent_color_default(self):
        pt = PostType.objects.create(name_en='Art', slug='art')
        # Default accent_color should be a valid hex
        self.assertTrue(pt.accent_color.startswith('#'))

    def test_posttype_slug_unique(self):
        PostType.objects.create(name_en='A', slug='dup')
        with self.assertRaises(Exception):
            PostType.objects.create(name_en='B', slug='dup')


# ---------------------------------------------------------------------------
# HTML sanitization: clean_post_body
# ---------------------------------------------------------------------------

class CleanPostBodyTests(TestCase):

    def test_empty_body_returns_empty(self):
        from .utils import clean_post_body
        self.assertEqual(clean_post_body(''), '')
        self.assertEqual(clean_post_body(None), '')

    def test_plain_text_passes_through(self):
        from .utils import clean_post_body
        text = 'Just plain text, no HTML.'
        self.assertEqual(clean_post_body(text), text)

    def test_script_tags_are_stripped(self):
        from .utils import clean_post_body
        html = '<p>Hello</p><script>alert("xss")</script>'
        result = clean_post_body(html)
        self.assertNotIn('<script>', result)
        self.assertIn('Hello', result)

    def test_onerror_attribute_is_stripped(self):
        from .utils import clean_post_body
        html = '<img src="valid.jpg" onerror="alert(1)">'
        result = clean_post_body(html)
        self.assertNotIn('onerror', result)

    def test_allowed_tags_preserved(self):
        from .utils import clean_post_body
        html = '<p><strong>Bold</strong> and <em>italic</em></p>'
        result = clean_post_body(html)
        self.assertIn('<strong>', result)
        self.assertIn('<em>', result)

    def test_disallowed_tags_stripped(self):
        from .utils import clean_post_body
        html = '<p>Text</p><iframe src="evil.com"></iframe>'
        result = clean_post_body(html)
        self.assertNotIn('<iframe>', result)

    def test_external_media_img_stripped(self):
        from .utils import clean_post_body
        html = '<img src="https://evil.com/track.gif">'
        result = clean_post_body(html)
        self.assertNotIn('evil.com', result)

    def test_local_media_img_allowed(self):
        from .utils import clean_post_body
        html = '<img src="/media/posts/image.jpg">'
        result = clean_post_body(html)
        self.assertIn('/media/posts/image.jpg', result)

    def test_data_uri_img_stripped(self):
        from .utils import clean_post_body
        html = '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7">'
        result = clean_post_body(html)
        self.assertNotIn('data:', result)

    def test_javascript_uri_stripped(self):
        from .utils import clean_post_body
        html = '<a href="javascript:alert(1)">Click</a>'
        result = clean_post_body(html)
        self.assertNotIn('javascript:', result)

    def test_noopener_added_to_blank_links(self):
        from .utils import clean_post_body
        html = '<a href="https://example.com" target="_blank">Link</a>'
        result = clean_post_body(html)
        self.assertIn('noopener', result)
        self.assertIn('noreferrer', result)

    def test_noopener_preserves_existing_rel(self):
        from .utils import clean_post_body
        html = '<a href="https://example.com" target="_blank" rel="nofollow">Link</a>'
        result = clean_post_body(html)
        self.assertIn('nofollow', result)
        self.assertIn('noopener', result)
        self.assertIn('noreferrer', result)

    def test_heading_ids_injected(self):
        from .utils import clean_post_body
        html = '<h2>Introduction</h2><p>Text</p>'
        result = clean_post_body(html)
        self.assertIn('id="introduction"', result)

    def test_oversized_body_raises_validation_error(self):
        from .utils import clean_post_body
        from django.core.exceptions import ValidationError
        huge = '<p>' + 'x' * 600_000 + '</p>'
        with self.assertRaises(ValidationError):
            clean_post_body(huge)


# ---------------------------------------------------------------------------
# _enforce_noopener
# ---------------------------------------------------------------------------

class EnforceNoopenerTests(TestCase):

    def test_adds_noopener_to_blank_link(self):
        from .utils import _enforce_noopener
        html = '<a href="/page" target="_blank">Link</a>'
        result = _enforce_noopener(html)
        self.assertIn('rel="noopener noreferrer"', result)

    def test_preserves_existing_nofollow(self):
        from .utils import _enforce_noopener
        html = '<a href="/page" target="_blank" rel="nofollow">Link</a>'
        result = _enforce_noopener(html)
        self.assertIn('nofollow', result)
        self.assertIn('noopener', result)

    def test_does_not_modify_non_blank_links(self):
        from .utils import _enforce_noopener
        html = '<a href="/page">Link</a>'
        result = _enforce_noopener(html)
        self.assertNotIn('rel=', result)

    def test_merges_multiple_existing_rel_values(self):
        from .utils import _enforce_noopener
        html = '<a href="/page" target="_blank" rel="nofollow sponsored">Link</a>'
        result = _enforce_noopener(html)
        self.assertIn('nofollow', result)
        self.assertIn('sponsored', result)
        self.assertIn('noopener', result)
        self.assertIn('noreferrer', result)


# ---------------------------------------------------------------------------
# _media_src_allowed
# ---------------------------------------------------------------------------

class MediaSrcAllowedTests(TestCase):

    def test_valid_local_path(self):
        from .utils import _media_src_allowed
        self.assertTrue(_media_src_allowed('/media/posts/image.jpg'))

    def test_absolute_url_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed('https://evil.com/image.jpg'))

    def test_data_uri_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed('data:image/jpeg;base64,abc'))

    def test_javascript_uri_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed('javascript:alert(1)'))

    def test_empty_src_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed(''))

    def test_traversal_attempt_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed('/media/posts/../../etc/passwd'))

    def test_url_encoded_traversal_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed('/media/posts/%2e%2e%2f%2e%2e%2fetc/passwd'))

    def test_query_string_stripped_for_extension(self):
        from .utils import _media_src_allowed
        self.assertTrue(_media_src_allowed('/media/posts/image.jpg?w=800'))

    def test_unsupported_extension_blocked(self):
        from .utils import _media_src_allowed
        self.assertFalse(_media_src_allowed('/media/posts/file.exe'))

    def test_inline_path_allowed(self):
        from .utils import _media_src_allowed
        self.assertTrue(_media_src_allowed('/media/posts/inline/abc.png'))


# ---------------------------------------------------------------------------
# classify_upload_file
# ---------------------------------------------------------------------------

class ClassifyUploadFileTests(TestCase):

    def test_image_extensions(self):
        from .utils import classify_upload_file
        self.assertEqual(classify_upload_file('photo.jpg'), 'image')
        self.assertEqual(classify_upload_file('photo.jpeg'), 'image')
        self.assertEqual(classify_upload_file('photo.png'), 'image')
        self.assertEqual(classify_upload_file('photo.gif'), 'image')
        self.assertEqual(classify_upload_file('photo.webp'), 'image')

    def test_audio_extensions(self):
        from .utils import classify_upload_file
        self.assertEqual(classify_upload_file('song.mp3'), 'audio')
        self.assertEqual(classify_upload_file('song.ogg'), 'audio')
        self.assertEqual(classify_upload_file('song.wav'), 'audio')

    def test_video_extensions(self):
        from .utils import classify_upload_file
        self.assertEqual(classify_upload_file('clip.mp4'), 'video')
        self.assertEqual(classify_upload_file('clip.webm'), 'video')

    def test_unknown_extension_returns_none(self):
        from .utils import classify_upload_file
        self.assertIsNone(classify_upload_file('file.exe'))
        self.assertIsNone(classify_upload_file('file.txt'))


# ---------------------------------------------------------------------------
# looks_like_html
# ---------------------------------------------------------------------------

class LooksLikeHTMLTests(TestCase):

    def test_plain_text(self):
        from .utils import looks_like_html
        self.assertFalse(looks_like_html('Hello world'))

    def test_html_paragraph(self):
        from .utils import looks_like_html
        self.assertTrue(looks_like_html('<p>Hello</p>'))

    def test_html_with_angle_brackets(self):
        from .utils import looks_like_html
        # Angle brackets without a tag name don't look like HTML
        self.assertFalse(looks_like_html('5 < 10 and 10 > 5'))
        self.assertTrue(looks_like_html('<div>content</div>'))


# ---------------------------------------------------------------------------
# slugify_heading
# ---------------------------------------------------------------------------

class SlugifyHeadingTests(TestCase):

    def test_simple_heading(self):
        from .utils import slugify_heading
        self.assertEqual(slugify_heading('Introduction'), 'introduction')

    def test_heading_with_spaces(self):
        from .utils import slugify_heading
        self.assertEqual(slugify_heading('Getting Started'), 'getting-started')

    def test_heading_with_special_chars(self):
        from .utils import slugify_heading
        self.assertEqual(slugify_heading('What is C++?'), 'what-is-c')

    def test_heading_with_persian(self):
        from .utils import slugify_heading
        result = slugify_heading('مقدمه')
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# detect_mime
# ---------------------------------------------------------------------------

class DetectMimeTests(TestCase):

    def test_returns_mime_for_valid_image(self):
        from io import BytesIO
        from .utils import detect_mime
        # Create a minimal valid JPEG
        buf = BytesIO()
        buf.write(b'\xff\xd8\xff\xe0' + b'\x00' * 100)  # JPEG header
        buf.name = 'test.jpg'
        result = detect_mime(buf)
        self.assertIsNotNone(result)

    def test_returns_none_for_empty_file(self):
        from io import BytesIO
        from .utils import detect_mime
        buf = BytesIO()
        buf.name = 'empty.bin'
        result = detect_mime(buf)
        # May return 'application/x-empty' or None depending on OS
        self.assertIn(result, [None, 'application/x-empty', 'inode/x-empty'])


# ---------------------------------------------------------------------------
# Post view tests
# ---------------------------------------------------------------------------

class PostDetailViewTests(TestCase):

    def setUp(self):
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')

    def test_published_post_exists_in_db(self):
        post = Post.objects.create(
            title='Detail Test', slug='detail-test', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )
        self.assertTrue(Post.objects.published().filter(slug='detail-test').exists())

    def test_unpublished_post_not_in_published_manager(self):
        Post.objects.create(
            title='Hidden', slug='hidden', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=False,
        )
        self.assertFalse(Post.objects.published().filter(slug='hidden').exists())


# ---------------------------------------------------------------------------
# Post list view tests
# ---------------------------------------------------------------------------

class PostListViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.url = reverse('posts:post_list')

    def tearDown(self):
        cache.clear()

    def test_post_list_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_category_filter(self):
        cat2 = Category.objects.create(name_en='Sports', name_fa='ورزش', slug='sports')
        Post.objects.create(
            title='News Post', slug='news-post', category=self.cat, post_type=self.pt,
            body='<p>A</p>', pub_date=timezone.now(), is_visible=True,
        )
        Post.objects.create(
            title='Sports Post', slug='sports-post', category=cat2, post_type=self.pt,
            body='<p>B</p>', pub_date=timezone.now(), is_visible=True,
        )
        resp = self.client.get(self.url, {'category': 'news'})
        # The main content should show News Post but not Sports Post
        html = resp.content.decode('utf-8')
        # Count occurrences in the news-archive-list (main content area)
        self.assertIn('News Post', html)

    def test_type_filter(self):
        pt2 = PostType.objects.create(name_en='Video', slug='video')
        Post.objects.create(
            title='Article Post', slug='article-post', category=self.cat, post_type=self.pt,
            body='<p>A</p>', pub_date=timezone.now(), is_visible=True,
        )
        Post.objects.create(
            title='Video Post', slug='video-post', category=self.cat, post_type=pt2,
            body='<p>B</p>', pub_date=timezone.now(), is_visible=True,
        )
        resp = self.client.get(self.url, {'type': 'video'})
        html = resp.content.decode('utf-8')
        self.assertIn('Video Post', html)


# ---------------------------------------------------------------------------
# Search view tests
# ---------------------------------------------------------------------------

class SearchViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.url = reverse('search:search')

    def tearDown(self):
        cache.clear()

    def test_empty_search_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_search_finds_matching_posts(self):
        Post.objects.create(
            title='Django Tutorial', slug='django-tutorial', category=self.cat, post_type=self.pt,
            body='<p>Learn Django</p>', summary='Django guide',
            pub_date=timezone.now(), is_visible=True,
        )
        Post.objects.create(
            title='Python Guide', slug='python-guide', category=self.cat, post_type=self.pt,
            body='<p>Learn Python</p>', summary='Python guide',
            pub_date=timezone.now(), is_visible=True,
        )
        resp = self.client.get(self.url, {'q': 'Django'})
        html = resp.content.decode('utf-8')
        # The search results area should contain Django Tutorial
        self.assertIn('Django Tutorial', html)
        # Search result count should reflect matching posts
        self.assertIn('1 results found', html)

    def test_search_xss_in_query_not_reflected(self):
        resp = self.client.get(self.url, {'q': '<script>alert(1)</script>'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, '<script>alert(1)</script>')

    def test_search_sql_injection_attempt(self):
        resp = self.client.get(self.url, {'q': "1' OR '1'='1"})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# RSS Feed tests
# ---------------------------------------------------------------------------

class RSSFeedTests(TestCase):

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')

    def test_feed_returns_200(self):
        resp = self.client.get(reverse('posts:post_feed'))
        self.assertEqual(resp.status_code, 200)

    def test_feed_contains_post_title(self):
        Post.objects.create(
            title='Feed Post', slug='feed-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )
        resp = self.client.get(reverse('posts:post_feed'))
        self.assertContains(resp, 'Feed Post')


# ---------------------------------------------------------------------------
# Sitemap tests
# ---------------------------------------------------------------------------

class SitemapTests(TestCase):

    def test_sitemap_returns_200(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)

    def test_sitemap_contains_xml(self):
        resp = self.client.get('/sitemap.xml')
        self.assertContains(resp, '<?xml')
        self.assertContains(resp, 'urlset')


# ---------------------------------------------------------------------------
# Post view count tests
# ---------------------------------------------------------------------------

class PostViewCountTests(TestCase):

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.post = Post.objects.create(
            title='View Test', slug='view-test', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )

    def tearDown(self):
        cache.clear()

    def test_view_count_default_zero(self):
        self.assertEqual(self.post.view_count, 0)
        self.assertEqual(self.post.unique_view_count, 0)

    def test_view_count_increments_on_every_load(self):
        url = reverse('posts:post_detail', kwargs={'slug': self.post.slug})
        self.client.get(url)
        self.client.get(url)
        self.client.get(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 3)

    def test_unique_view_count_increments_once_per_ip(self):
        url = reverse('posts:post_detail', kwargs={'slug': self.post.slug})
        self.client.get(url)
        self.client.get(url)
        self.client.get(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.unique_view_count, 1)

    def test_different_ips_increment_both_counts(self):
        url = reverse('posts:post_detail', kwargs={'slug': self.post.slug})
        self.client.get(url, REMOTE_ADDR='192.168.1.1')
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)
        self.assertEqual(self.post.unique_view_count, 1)

        # Different IP - same session
        self.client.get(url, REMOTE_ADDR='192.168.1.2')
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 2)
        self.assertEqual(self.post.unique_view_count, 2)

    def test_view_count_visible_to_all_users(self):
        self.post.view_count = 42
        self.post.save()
        
        # Anonymous user should see view count
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertContains(resp, '43')  # incremented by 1
        
        # Regular user should see view count
        user = User.objects.create_user(
            username='regular', password='pass123', email='regular@example.com'
        )
        self.client.force_login(user)
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertContains(resp, 'views')

    def test_unique_view_count_visible_only_to_superuser(self):
        self.post.unique_view_count = 10
        self.post.save()
        
        # Regular user should not see unique view count
        user = User.objects.create_user(
            username='regular', password='pass123', email='regular@example.com'
        )
        self.client.force_login(user)
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertNotContains(resp, 'unique')
        
        # Superuser should see unique view count
        admin = User.objects.create_superuser(
            username='admin', password='pass123', email='admin@example.com'
        )
        self.client.force_login(admin)
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertContains(resp, 'unique')


# ---------------------------------------------------------------------------
# Markdown body mode tests
# ---------------------------------------------------------------------------

class MarkdownBodyModeTests(TestCase):
    """Tests for dual-mode post body: Quill write vs .md file upload."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='pass123', email='admin@example.com'
        )
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name_en='Tech', name_fa='تکنولوژی', slug='tech')
        self.pt = PostType.objects.create(name_en='Article', slug='article')

    def _make_md_file(self, content='Hello **world**', name='test.md'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/markdown')

    def test_post_with_md_file_renders_markdown(self):
        post = Post.objects.create(
            title='MD Post', slug='md-post', category=self.cat, post_type=self.pt,
            body='<p>fallback</p>', body_md_file=self._make_md_file(),
            pub_date=timezone.now(), is_visible=True,
        )
        from .templatetags.post_extras import render_body_for_post
        result = render_body_for_post(post)
        self.assertIn('<strong>world</strong>', result)
        self.assertNotIn('<p>fallback</p>', result)

    def test_post_without_md_file_renders_body(self):
        post = Post.objects.create(
            title='HTML Post', slug='html-post', category=self.cat, post_type=self.pt,
            body='<p>Hello</p>', pub_date=timezone.now(), is_visible=True,
        )
        from .templatetags.post_extras import render_body_for_post
        result = render_body_for_post(post)
        self.assertIn('Hello', result)

    def test_form_upload_mode_requires_md_file(self):
        """When body_mode=upload_md but no file is uploaded, the error should
        be on body_md_file (not body)."""
        from .forms import PostForm
        data = {
            'title': 'Test', 'slug': 'test', 'category': self.cat.pk,
            'post_type': self.pt.pk, 'body_mode': 'upload_md',
            'author_name': 'Author', 'summary': '',
        }
        form = PostForm(data=data, files={})
        self.assertFalse(form.is_valid())
        self.assertIn('body_md_file', form.errors)

    def test_form_write_mode_requires_body(self):
        from .forms import PostForm
        data = {
            'title': 'Test', 'slug': 'test', 'category': self.cat.pk,
            'post_type': self.pt.pk, 'body_mode': 'write',
            'body': '', 'author_name': 'Author', 'summary': '',
        }
        form = PostForm(data=data, files={})
        self.assertFalse(form.is_valid())
        self.assertIn('body', form.errors)

    def test_clean_body_md_file_rejects_non_md(self):
        from .forms import PostForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        data = {
            'title': 'Test', 'slug': 'test', 'category': self.cat.pk,
            'post_type': self.pt.pk, 'body_mode': 'upload_md',
            'author_name': 'Author', 'summary': '',
        }
        form = PostForm(data=data, files={'body_md_file': bad_file})
        self.assertFalse(form.is_valid())
        self.assertIn('body_md_file', form.errors)

    def test_clean_body_md_file_rejects_oversized(self):
        from .forms import PostForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        big_file = SimpleUploadedFile('big.md', b'x' * (1 * 1024 * 1024 + 1), content_type='text/markdown')
        data = {
            'title': 'Test', 'slug': 'test', 'category': self.cat.pk,
            'post_type': self.pt.pk, 'body_mode': 'upload_md',
            'author_name': 'Author', 'summary': '',
        }
        form = PostForm(data=data, files={'body_md_file': big_file})
        self.assertFalse(form.is_valid())
        self.assertIn('body_md_file', form.errors)

    def test_render_markdown_body_sanitizes_xss(self):
        from .utils.sanitization import render_markdown_body
        result = render_markdown_body('<p>Hello</p><script>alert(1)</script>')
        self.assertNotIn('<script>', result)
        self.assertIn('Hello', result)

    def test_render_markdown_body_renders_fenced_code(self):
        from .utils.sanitization import render_markdown_body
        md = '```python\nprint("hi")\n```'
        result = render_markdown_body(md)
        self.assertIn('<pre>', result)
        self.assertIn('code', result)

    def test_render_markdown_body_renders_tables(self):
        from .utils.sanitization import render_markdown_body
        md = '| A | B |\n|---|---|\n| 1 | 2 |'
        result = render_markdown_body(md)
        self.assertIn('<table>', result)

    def test_edit_post_with_existing_md_file_defaults_mode(self):
        post = Post.objects.create(
            title='Existing MD', slug='existing-md', category=self.cat, post_type=self.pt,
            body='<p>fallback</p>', body_md_file=self._make_md_file(),
            pub_date=timezone.now(), is_visible=True,
        )
        from .forms import PostForm
        form = PostForm(instance=post)
        self.assertEqual(form.fields['body_mode'].initial, 'upload_md')

    def test_post_detail_view_renders_md_file(self):
        post = Post.objects.create(
            title='View MD', slug='view-md', category=self.cat, post_type=self.pt,
            body='<p>fallback</p>', body_md_file=self._make_md_file('## Hello'),
            pub_date=timezone.now(), is_visible=True,
        )
        url = reverse('posts:post_detail', kwargs={'slug': post.slug})
        resp = self.client.get(url)
        self.assertContains(resp, '<h2')
        self.assertContains(resp, 'Hello')

    def test_post_detail_view_renders_html_body_when_no_md(self):
        post = Post.objects.create(
            title='View HTML', slug='view-html', category=self.cat, post_type=self.pt,
            body='<p>Hello HTML</p>', pub_date=timezone.now(), is_visible=True,
        )
        url = reverse('posts:post_detail', kwargs={'slug': post.slug})
        resp = self.client.get(url)
        self.assertContains(resp, 'Hello HTML')


# ═══════════════════════════════════════════════════════════
# Markdown Extensions Tests (Nineteenth Pass)
# ═══════════════════════════════════════════════════════════

class AdmonitionTests(TestCase):
    """Tests for !!! note / !!! warning admonition blocks."""

    def test_basic_note_admonition(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! note\n    This is a note.'
        result = render_markdown_body(md)
        self.assertIn('class="admonition note"', result)
        self.assertIn('class="admonition-title"', result)
        self.assertIn('This is a note.', result)

    def test_warning_admonition(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! warning\n    Be careful!'
        result = render_markdown_body(md)
        self.assertIn('class="admonition warning"', result)
        self.assertIn('Be careful!', result)

    def test_danger_admonition(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! danger\n    Critical!'
        result = render_markdown_body(md)
        self.assertIn('class="admonition danger"', result)

    def test_custom_title(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! tip "Pro Tip"\n    Use shortcuts.'
        result = render_markdown_body(md)
        self.assertIn('class="admonition tip"', result)
        self.assertIn('Pro Tip', result)

    def test_empty_title(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! important ""\n    No title bar.'
        result = render_markdown_body(md)
        self.assertIn('class="admonition important"', result)
        self.assertNotIn('admonition-title', result)

    def test_multiline_body(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! note\n    First paragraph.\n\n    Second paragraph.'
        result = render_markdown_body(md)
        self.assertIn('First paragraph.', result)
        self.assertIn('Second paragraph.', result)

    def test_admonition_survives_bleach(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! note\n    Content here.'
        result = render_markdown_body(md)
        self.assertIn('admonition', result)
        self.assertIn('admonition-title', result)

    def test_all_types_produce_valid_html(self):
        from .utils.sanitization import render_markdown_body
        types = ['note', 'warning', 'danger', 'tip', 'info', 'hint',
                 'attention', 'caution', 'error', 'important']
        for admonition_type in types:
            md = f'!!! {admonition_type}\n    Content.'
            result = render_markdown_body(md)
            self.assertIn(f'class="admonition {admonition_type}"', result,
                          f'Failed for type: {admonition_type}')


class MathTests(TestCase):
    """Tests for LaTeX math via pymdownx.arithmatex (generic mode)."""

    def test_inline_math_dollar(self):
        from .utils.sanitization import render_markdown_body
        md = 'Math: $x^2$'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('x^2', result)

    def test_inline_math_round(self):
        from .utils.sanitization import render_markdown_body
        md = r'Math: \(e^{i\pi}\)'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('e^{i\\pi}', result)

    def test_block_math_double_dollar(self):
        from .utils.sanitization import render_markdown_body
        md = '$$\nE = mc^2\n$$'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('E = mc^2', result)

    def test_block_math_square(self):
        from .utils.sanitization import render_markdown_body
        md = r'\[E = mc^2\]'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('E = mc^2', result)

    def test_aligned_equations(self):
        from .utils.sanitization import render_markdown_body
        md = '$$\n\\begin{align}\na &= b \\\\\nc &= d\n\\end{align}\n$$'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('\\begin{align}', result)

    def test_math_in_span_container(self):
        from .utils.sanitization import render_markdown_body
        md = 'Inline $x^2$ here.'
        result = render_markdown_body(md)
        self.assertIn('<span class="arithmatex">', result)

    def test_math_in_div_container(self):
        from .utils.sanitization import render_markdown_body
        md = '$$\nx^2\n$$'
        result = render_markdown_body(md)
        self.assertIn('<div class="arithmatex">', result)

    def test_math_no_script_tags(self):
        """Generic mode must NOT produce <script> tags (security)."""
        from .utils.sanitization import render_markdown_body
        md = 'Math $x^2$ and $$y^2$$'
        result = render_markdown_body(md)
        self.assertNotIn('<script', result)

    def test_math_survives_bleach(self):
        from .utils.sanitization import render_markdown_body
        md = 'Math $x^2$'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)

    def test_complex_formula(self):
        from .utils.sanitization import render_markdown_body
        md = '$$\\sum_{i=1}^{n} i^2 = \\frac{n(n+1)(2n+1)}{6}$$'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('\\sum', result)
        self.assertIn('\\frac', result)


class SyntaxHighlightTests(TestCase):
    """Tests for pymdownx.highlight code block rendering."""

    def test_python_code_block(self):
        from .utils.sanitization import render_markdown_body
        md = '```python\nprint("hello")\n```'
        result = render_markdown_body(md)
        self.assertIn('highlight', result)
        self.assertIn('print', result)

    def test_javascript_code_block(self):
        from .utils.sanitization import render_markdown_body
        md = '```javascript\nconst x = 1;\n```'
        result = render_markdown_body(md)
        self.assertIn('highlight', result)
        self.assertIn('const', result)

    def test_bash_code_block(self):
        from .utils.sanitization import render_markdown_body
        md = '```bash\necho "hi"\n```'
        result = render_markdown_body(md)
        self.assertIn('highlight', result)

    def test_plain_code_block(self):
        from .utils.sanitization import render_markdown_body
        md = '```\nplain code\n```'
        result = render_markdown_body(md)
        self.assertIn('<pre>', result)

    def test_highlight_has_pre_tag(self):
        from .utils.sanitization import render_markdown_body
        md = '```python\nx = 1\n```'
        result = render_markdown_body(md)
        self.assertIn('<pre>', result)
        self.assertIn('<code', result)

    def test_code_survives_bleach(self):
        from .utils.sanitization import render_markdown_body
        md = '```python\ndef foo(): pass\n```'
        result = render_markdown_body(md)
        self.assertIn('highlight', result)
        self.assertIn('foo', result)


class MarkdownIntegrationTests(TestCase):
    """Integration tests combining multiple markdown features."""

    def test_admonition_with_code(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! note\n    Code example:\n\n    ```python\n    x = 1\n    ```'
        result = render_markdown_body(md)
        self.assertIn('admonition', result)
        self.assertIn('highlight', result)

    def test_admonition_with_math(self):
        from .utils.sanitization import render_markdown_body
        md = '!!! tip\n    Use $x^2$ for squares.'
        result = render_markdown_body(md)
        self.assertIn('admonition', result)
        self.assertIn('arithmatex', result)

    def test_table_with_math(self):
        from .utils.sanitization import render_markdown_body
        md = '| Formula |\n|---------|\n| $x^2$ |'
        result = render_markdown_body(md)
        self.assertIn('<table>', result)
        self.assertIn('arithmatex', result)

    def test_full_document_rendering(self):
        """Test that a complex document renders without errors."""
        from .utils.sanitization import render_markdown_body
        md = """# Title

!!! note
    Important info.

Some math: $e^{i\\pi} = -1$

```python
x = 42
```

| A | B |
|---|---|
| 1 | 2 |
"""
        result = render_markdown_body(md)
        self.assertIn('admonition', result)
        self.assertIn('arithmatex', result)
        self.assertIn('highlight', result)
        self.assertIn('<table>', result)

    def test_xss_in_admonition(self):
        """XSS inside admonition should be sanitized."""
        from .utils.sanitization import render_markdown_body
        md = '!!! note\n    <script>alert("xss")</script>'
        result = render_markdown_body(md)
        self.assertNotIn('<script>', result)
        self.assertIn('admonition', result)

    def test_xss_in_math(self):
        """XSS inside math delimiters should be sanitized."""
        from .utils.sanitization import render_markdown_body
        md = '$<script>alert("xss")</script>$'
        result = render_markdown_body(md)
        self.assertNotIn('<script>', result)

    def test_markdown_body_file_with_admonitions(self):
        """Full pipeline: markdown file with admonitions through render_markdown_body."""
        from .utils.sanitization import render_markdown_body
        md = '!!! warning\n    **Bold** and *italic* in admonition.'
        result = render_markdown_body(md)
        self.assertIn('admonition', result)
        self.assertIn('<strong>', result)
        self.assertIn('<em>', result)

    def test_markdown_body_file_with_full_math(self):
        """Full pipeline: markdown file with math through render_markdown_body."""
        from .utils.sanitization import render_markdown_body
        md = '$$\\int_0^1 x^2 \\, dx = \\frac{1}{3}$$'
        result = render_markdown_body(md)
        self.assertIn('arithmatex', result)
        self.assertIn('\\int', result)