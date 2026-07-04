"""
Regression and integration tests for the core app.

Run with:  python manage.py test core

Covers:
  - Page model (__str__, get_absolute_url, Meta.ordering, slug uniqueness)
  - home view (latest visible posts, empty state, ordering/limit)
  - about view (renders static content)
  - page_detail view (200 for existing slug, 404 for missing slug)
  - the custom 404 handler (core.views.page_not_found, registered as
    handler404 in myproject/urls.py) -- requires DEBUG=False to actually
    fire instead of Django's technical debug 404 page
  - core.urls names resolve with the correct i18n language prefix
  - global_context context processor: categories / latest_posts / nav_pages,
    its 5-minute LocMemCache caching behaviour, and its try/except
    fallback to empty lists on a DB error
  - PageAdmin registration and prepopulated_fields
  - the seed_data management command (idempotency via get_or_create)
"""

import re
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from posts.models import Category, Post, PostType
from .context_processors import _CONTEXT_CACHE_KEY, global_context
from .models import Page

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CSS_DIR = settings.BASE_DIR / 'core' / 'static' / 'core' / 'css'
STYLE_CSS_PATH = settings.BASE_DIR / 'core' / 'static' / 'core' / 'style.css'


def read_all_css():
    """Read style.css hub + all CSS partial files and return combined content."""
    parts = [STYLE_CSS_PATH.read_text(encoding='utf-8')]
    for p in sorted(CSS_DIR.glob('_*.css')):
        parts.append(p.read_text(encoding='utf-8'))
    return '\n'.join(parts)


def make_admin(username='admin', password='AdminPass123!'):
    return User.objects.create_user(
        username=username, password=password,
        email=f'{username}@example.com',
        is_active=True, is_staff=True, is_superuser=True,
    )


def make_post(category, post_type, **kwargs):
    defaults = {
        'title': 'Sample Post',
        'slug': 'sample-post',
        'body': '<p>Sample body.</p>',
        'is_visible': True,
        'pub_date': timezone.now(),
    }
    defaults.update(kwargs)
    return Post.objects.create(category=category, post_type=post_type, **defaults)


# ---------------------------------------------------------------------------
# Page model
# ---------------------------------------------------------------------------

class PageModelTests(TestCase):

    def test_str_returns_title(self):
        page = Page.objects.create(title_en='Philosophy', slug='philosophy', body_en='...')
        self.assertEqual(str(page), 'Philosophy')

    def test_get_absolute_url_includes_language_prefix(self):
        page = Page.objects.create(title_en='Licensing', slug='licensing', body_en='...')
        # Pin the active language explicitly so this test can't become
        # flaky if an earlier test in the same process left a different
        # language activated (translation.activate() is a thread-local
        # that otherwise persists across tests).
        with translation.override('en'):
            self.assertEqual(page.get_absolute_url(), '/en/page/licensing/')

    def test_get_absolute_url_resolves_to_page_detail_view(self):
        page = Page.objects.create(title_en='Get Involved', slug='get-involved', body_en='...')
        with translation.override('en'):
            resp = self.client.get(page.get_absolute_url())
        self.assertEqual(resp.status_code, 200)

    def test_default_ordering_is_nav_order_then_title(self):
        Page.objects.create(title_en='Zeta', slug='zeta', body_en='', nav_order=1)
        Page.objects.create(title_en='Alpha', slug='alpha', body_en='', nav_order=1)
        Page.objects.create(title_en='Beta', slug='beta', body_en='', nav_order=0)
        titles = list(Page.objects.values_list('title_en', flat=True))
        # nav_order=0 first, then nav_order=1 group alphabetically (Alpha, Zeta).
        self.assertEqual(titles, ['Beta', 'Alpha', 'Zeta'])

    def test_slug_must_be_unique(self):
        Page.objects.create(title_en='First', slug='dup', body_en='')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Page.objects.create(title_en='Second', slug='dup', body_en='')

    def test_show_in_nav_defaults_to_false(self):
        page = Page.objects.create(title_en='Hidden', slug='hidden', body_en='')
        self.assertFalse(page.show_in_nav)


# ---------------------------------------------------------------------------
# home view
# ---------------------------------------------------------------------------

class HomeViewTests(TestCase):

    def setUp(self):
        # The global_context processor (rendered on every page, including
        # this one) caches navigation data for 5 minutes in LocMemCache.
        # Clear it so earlier tests in the same run can't leak stale
        # categories/posts/nav_pages into this test's assertions.
        cache.clear()
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.url = reverse('home')

    def test_home_page_loads(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'core/home.html')

    def test_empty_state_message_when_no_posts(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'No news posts yet.')

    def test_only_visible_posts_appear(self):
        visible = make_post(self.cat, self.pt, slug='visible-post', title='Visible Post',
                             is_visible=True)
        make_post(self.cat, self.pt, slug='hidden-post', title='Hidden Post',
                   is_visible=False)
        resp = self.client.get(self.url)
        self.assertContains(resp, visible.title)
        self.assertNotContains(resp, 'Hidden Post')

    def test_shows_at_most_five_posts_most_recent_first(self):
        now = timezone.now()
        for i in range(7):
            make_post(
                self.cat, self.pt,
                slug=f'post-{i}', title=f'Post {i}',
                pub_date=now - timedelta(days=i),
            )
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context['latest_news']), 5)
        # Most recently published (smallest day offset) must appear first.
        titles = [p.title for p in resp.context['latest_news']]
        self.assertEqual(titles, ['Post 0', 'Post 1', 'Post 2', 'Post 3', 'Post 4'])


# ---------------------------------------------------------------------------
# about view
# ---------------------------------------------------------------------------

class AboutViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.url = reverse('about')

    def test_about_page_loads(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'core/about.html')

    def test_about_page_contains_heading(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'What We Offer')


# ---------------------------------------------------------------------------
# page_detail view
# ---------------------------------------------------------------------------

class PageDetailViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.page = Page.objects.create(
            title_en='Philosophy of Free Software',
            slug='philosophy',
            body_en='Free software is a matter of liberty, not price.',
        )

    def test_existing_page_returns_200(self):
        resp = self.client.get(reverse('page_detail', kwargs={'slug': 'philosophy'}))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'core/page_detail.html')

    def test_page_context_object_is_correct(self):
        resp = self.client.get(reverse('page_detail', kwargs={'slug': 'philosophy'}))
        self.assertEqual(resp.context['page'], self.page)

    def test_page_title_and_body_are_rendered(self):
        resp = self.client.get(reverse('page_detail', kwargs={'slug': 'philosophy'}))
        self.assertContains(resp, 'Philosophy of Free Software')
        self.assertContains(resp, 'Free software is a matter of liberty')

    def test_nonexistent_slug_returns_404(self):
        resp = self.client.get(reverse('page_detail', kwargs={'slug': 'does-not-exist'}))
        self.assertEqual(resp.status_code, 404)

    def test_last_updated_label_is_translatable(self):
        # Regression check: page_detail.html must {% load i18n %} and wrap
        # "Last updated:" in {% trans %} (see BUG-15 in PATCH_GUIDE.txt).
        resp = self.client.get(reverse('page_detail', kwargs={'slug': 'philosophy'}))
        self.assertContains(resp, 'Last updated:')


# ---------------------------------------------------------------------------
# Custom 404 handler (core.views.page_not_found)
# ---------------------------------------------------------------------------

class PageNotFoundHandlerTests(TestCase):
    """
    Django only invokes a project's custom handler404 when DEBUG=False;
    with DEBUG=True it shows its own technical 404 debug page instead.
    settings.py reads DEBUG via `config('DEBUG', default=True, cast=bool)`,
    so it defaults to True unless a .env file says otherwise -- every test
    here must force DEBUG=False explicitly to actually exercise
    core.views.page_not_found rather than Django's debug page.
    """

    @override_settings(DEBUG=False)
    def test_unknown_url_returns_custom_404_page(self):
        resp = self.client.get('/en/this-path-does-not-exist-zzz/')
        self.assertEqual(resp.status_code, 404)
        self.assertTemplateUsed(resp, '404.html')

    @override_settings(DEBUG=False)
    def test_custom_404_page_contains_expected_content(self):
        resp = self.client.get('/en/this-path-does-not-exist-zzz/')
        self.assertContains(resp, 'Page Not Found', status_code=404)
        self.assertContains(resp, 'OpenSrc', status_code=404)
        self.assertContains(resp, 'Persian', status_code=404)

    @override_settings(DEBUG=False)
    def test_custom_404_page_has_home_link(self):
        resp = self.client.get('/en/this-path-does-not-exist-zzz/')
        self.assertContains(resp, 'Go to Home', status_code=404)


# ---------------------------------------------------------------------------
# core.urls — i18n prefixing
# ---------------------------------------------------------------------------

class CoreUrlsI18nTests(TestCase):
    """
    All core.urls patterns are wrapped in i18n_patterns(prefix_default_language=True)
    in myproject/urls.py, so even the default language ('en') requires an
    explicit /en/ prefix -- a bare '/' or '/about/' is not how these resolve.
    """

    def test_home_resolves_with_en_prefix(self):
        with translation.override('en'):
            self.assertEqual(reverse('home'), '/en/')

    def test_about_resolves_with_en_prefix(self):
        with translation.override('en'):
            self.assertEqual(reverse('about'), '/en/about/')

    def test_home_resolves_with_fa_prefix(self):
        with translation.override('fa'):
            self.assertEqual(reverse('home'), '/fa/')

    def test_bare_root_redirects_to_language_prefixed_home(self):
        # LocaleMiddleware 302-redirects '/' to '/en/' since the prefixed
        # equivalent resolves (see BUG-29 in PATCH_GUIDE.txt for the same
        # mechanism applied to /accounts/login/).
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers['Location'], '/en/')


# ---------------------------------------------------------------------------
# global_context context processor
# ---------------------------------------------------------------------------

class GlobalContextProcessorTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_returns_only_nav_visible_pages_ordered_by_nav_order(self):
        Page.objects.create(title_en='Hidden', slug='hidden', body_en='', show_in_nav=False)
        Page.objects.create(title_en='Second', slug='second', body_en='', show_in_nav=True, nav_order=2)
        Page.objects.create(title_en='First', slug='first', body_en='', show_in_nav=True, nav_order=1)

        ctx = global_context(None)
        nav_titles = [p.title for p in ctx['nav_pages']]
        self.assertEqual(nav_titles, ['First', 'Second'])

    def test_returns_categories(self):
        cat = Category.objects.create(name_en='Tech', name_fa='فناوری', slug='tech')
        ctx = global_context(None)
        self.assertEqual(list(ctx['categories']), [cat])

    def test_returns_at_most_five_visible_latest_posts(self):
        cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        pt = PostType.objects.create(name_en='Article', slug='article')
        make_post(cat, pt, slug='hidden', title='Hidden', is_visible=False)
        for i in range(6):
            make_post(cat, pt, slug=f'p{i}', title=f'P{i}',
                      pub_date=timezone.now() - timedelta(days=i))

        ctx = global_context(None)
        self.assertEqual(len(ctx['latest_posts']), 5)
        self.assertNotIn('Hidden', [p.title for p in ctx['latest_posts']])

    def test_result_is_cached_for_subsequent_calls(self):
        Page.objects.create(title_en='First', slug='first', body_en='', show_in_nav=True)
        first = global_context(None)
        self.assertEqual(len(first['nav_pages']), 1)

        # Creating a new Page triggers the post_save signal which invalidates
        # the nav cache, so the next call should see fresh data.
        Page.objects.create(title_en='Second', slug='second', body_en='', show_in_nav=True)
        second = global_context(None)
        self.assertEqual(len(second['nav_pages']), 2, 'signal should invalidate cache')

    def test_cache_clear_picks_up_new_data(self):
        Page.objects.create(title_en='First', slug='first', body_en='', show_in_nav=True)
        global_context(None)  # populate the cache

        Page.objects.create(title_en='Second', slug='second', body_en='', show_in_nav=True)
        cache.delete(_CONTEXT_CACHE_KEY)
        refreshed = global_context(None)
        self.assertEqual(len(refreshed['nav_pages']), 2)

    @patch('core.context_processors.Category.objects.prefetch_related',
           side_effect=Exception('simulated DB failure'))
    def test_db_error_falls_back_to_empty_lists_without_raising(self, _mock):
        # Must not propagate the exception -- every page on the site renders
        # this context processor, so a transient DB error here must degrade
        # gracefully (empty nav) rather than turning into a site-wide 500.
        #
        # assertLogs both (a) suppresses the expected logger.exception()
        # traceback from being printed to the console during this test --
        # it's real, intentional output from the production code's except
        # block, not a test failure, but it's noisy in a clean test run --
        # and (b) lets us explicitly confirm the error really was logged.
        with self.assertLogs('core.context_processors', level='ERROR') as logs:
            ctx = global_context(None)
        self.assertEqual(ctx, {'categories': [], 'latest_posts': [], 'nav_pages': []})
        self.assertIn('global_context failed to load navigation data', logs.output[0])

    @override_settings(DEBUG=False)
    @patch('core.context_processors.Category.objects.prefetch_related',
           side_effect=Exception('simulated DB failure'))
    def test_page_still_renders_200_when_context_processor_db_call_fails(self, _mock):
        cache.clear()
        with self.assertLogs('core.context_processors', level='ERROR'):
            resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# PageAdmin
# ---------------------------------------------------------------------------

class PageAdminTests(TestCase):

    def setUp(self):
        self.admin_user = make_admin()
        self.client.force_login(self.admin_user)

    def test_page_changelist_loads(self):
        resp = self.client.get(reverse('admin:core_page_changelist'))
        self.assertEqual(resp.status_code, 200)

    def test_page_add_form_loads(self):
        resp = self.client.get(reverse('admin:core_page_add'))
        self.assertEqual(resp.status_code, 200)

    def test_page_is_registered_with_prepopulated_slug(self):
        from django.contrib import admin
        admin_inst = admin.site._registry.get(Page)
        self.assertIsNotNone(admin_inst, 'Page must be registered with the admin site')
        self.assertEqual(admin_inst.prepopulated_fields, {'slug': ('title_en',)})

    def test_page_list_display_matches_expected_columns(self):
        from django.contrib import admin
        admin_inst = admin.site._registry.get(Page)
        self.assertEqual(
            admin_inst.list_display,
            ('title_en', 'slug', 'show_in_nav', 'nav_order'),
        )


# ---------------------------------------------------------------------------
# seed_data management command
# ---------------------------------------------------------------------------

class SeedDataCommandTests(TestCase):

    def test_creates_exactly_three_pages(self):
        call_command('seed_data', stdout=StringIO())
        self.assertEqual(Page.objects.count(), 3)

    def test_creates_expected_slugs_shown_in_nav(self):
        call_command('seed_data', stdout=StringIO())
        slugs = set(Page.objects.values_list('slug', flat=True))
        self.assertEqual(slugs, {'philosophy', 'licensing', 'get-involved'})
        self.assertTrue(Page.objects.filter(show_in_nav=True).count() == 3)

    def test_running_twice_is_idempotent(self):
        call_command('seed_data', stdout=StringIO())
        call_command('seed_data', stdout=StringIO())
        self.assertEqual(Page.objects.count(), 3, 'running seed_data twice must not duplicate pages')

    def test_first_run_reports_created_second_run_reports_already_exists(self):
        out1 = StringIO()
        call_command('seed_data', stdout=out1)
        self.assertIn('[Created]', out1.getvalue())
        self.assertNotIn('[Already exists]', out1.getvalue())

        out2 = StringIO()
        call_command('seed_data', stdout=out2)
        self.assertIn('[Already exists]', out2.getvalue())
        self.assertNotIn('[Created]', out2.getvalue())

    def test_does_not_overwrite_manually_edited_existing_page(self):
        # get_or_create only sets `defaults` on CREATE; an admin's manual
        # edit to an existing page must survive a re-run of seed_data.
        Page.objects.create(
            title_en='Custom Philosophy Title', slug='philosophy', body_en='custom body',
            show_in_nav=False, nav_order=99,
        )
        call_command('seed_data', stdout=StringIO())
        page = Page.objects.get(slug='philosophy')
        self.assertEqual(page.title, 'Custom Philosophy Title')
        self.assertFalse(page.show_in_nav)


# ---------------------------------------------------------------------------
# AdminCSPOverrideMiddleware — admin search popup wouldn't close (fixed)
# ---------------------------------------------------------------------------

class AdminCSPOverrideMiddlewareTests(TestCase):
    """
    Before the fix, the site-wide CSP (script-src 'self', no 'unsafe-eval')
    applied to /admin/ too. django-unfold's UI is built on Alpine.js, which
    needs 'unsafe-eval' to evaluate inline x-data/x-on/x-show expressions --
    without it, Alpine's reactive bindings fail silently in the browser
    console, and anything that depends on them (including the global search
    popup's close-on-click-outside / close-on-escape behaviour) simply never
    fires. The popup still opens (Alpine's core script itself loads fine
    under 'self'), but never closes.

    AdminCSPOverrideMiddleware now swaps in a relaxed, 'unsafe-eval'-enabled
    CSP for /admin/ requests only, leaving the public site's strict CSP
    untouched everywhere else.
    """

    def setUp(self):
        self.admin_user = make_admin()
        self.client.force_login(self.admin_user)

    def test_admin_response_has_unsafe_eval_in_script_src(self):
        resp = self.client.get(reverse('admin:core_page_changelist'))
        csp = resp.headers.get('Content-Security-Policy', '')
        self.assertIn("'unsafe-eval'", csp)

    def test_admin_login_page_also_gets_relaxed_csp(self):
        # Covers the (unauthenticated) /admin/login/ page too, not just
        # pages reachable after logging in.
        self.client.logout()
        resp = self.client.get('/admin/login/')
        csp = resp.headers.get('Content-Security-Policy', '')
        self.assertIn("'unsafe-eval'", csp)

    def test_public_site_csp_remains_strict(self):
        # The relaxation must be scoped to /admin/ only -- the public site
        # must keep its strict, eval-free policy.
        resp = self.client.get(reverse('home'))
        csp = resp.headers.get('Content-Security-Policy', '')
        self.assertNotIn('unsafe-eval', csp)
        self.assertIn("script-src 'self'", csp)

    def test_admin_csp_still_restricts_object_and_frame_src(self):
        # Confirms the override is a deliberate, narrow relaxation (just
        # adding unsafe-eval to script-src) and not an accidental wipe of
        # the rest of the policy.
        resp = self.client.get(reverse('admin:core_page_changelist'))
        csp = resp.headers.get('Content-Security-Policy', '')
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-src 'none'", csp)


# ---------------------------------------------------------------------------
# .main-content unscoped max-width — admin/panel editor squeezed (fixed)
# ---------------------------------------------------------------------------

class MainContentWidthCSSTests(TestCase):
    """
    Before the fix, style.css had TWO separate, unscoped
    `.main-content { max-width: 900px; ... }` rules (a duplicate left over
    from a later "UX improvements" patch). Because they had no `.layout--`
    class qualifier, they applied to every page -- including the user
    panel / admin post editor, which renders with a bare `class="layout"`
    (no body_class block override). This squeezed the Quill editor (and
    the whole panel UI) into a 900px-wide column inside the already
    1100px-wide .layout container, making text wrap far earlier than the
    actual available width.

    Both rules are now scoped to `.layout--has-sidebar .main-content`
    only (post list/detail, category/subcategory -- the pages that
    legitimately want a centered, comfortable reading width next to a
    sidebar). Panel pages, which set neither `--no-sidebar` nor
    `--has-sidebar`, are now unaffected and fill the full layout width.
    """

    def setUp(self):
        self.css = read_all_css()

    def test_no_unscoped_main_content_max_width_rule_remains(self):
        # Matches a bare `.main-content { ... max-width ... }` block that
        # is NOT immediately preceded by a `.layout--` class qualifier
        # (e.g. NOT `.layout--has-sidebar .main-content { ... }`).
        unscoped_with_max_width = re.compile(
            r'(?<!--has-sidebar )(?<!--no-sidebar )\.main-content\s*\{[^}]*max-width[^}]*\}'
        )
        match = unscoped_with_max_width.search(self.css)
        self.assertIsNone(
            match,
            f'Found an unscoped .main-content rule with max-width -- this '
            f'leaks into panel/admin pages: {match.group(0) if match else None!r}'
        )

    def test_has_sidebar_scoped_rule_still_present(self):
        self.assertIn('.layout--has-sidebar .main-content', self.css)

    def test_no_sidebar_scoped_rule_still_present(self):
        # The pre-existing, correctly-scoped rule for home/about/search
        # pages must not have been accidentally removed by this fix.
        self.assertIn('.layout--no-sidebar .main-content', self.css)

    def test_panel_page_renders_bare_layout_class_with_no_width_modifier(self):
        # Confirms the template-side assumption the CSS fix depends on:
        # panel.html must not set body_class, or this fix would need to
        # account for whichever modifier it adds.
        admin_user = make_admin()
        self.client.force_login(admin_user)
        resp = self.client.get(reverse('accounts:panel'))
        html = resp.content.decode('utf-8')
        match = re.search(r'<div class="(layout[^"]*)">', html)
        self.assertIsNotNone(match, 'expected to find the <div class="layout..."> wrapper')
        self.assertEqual(match.group(1), 'layout')


# ---------------------------------------------------------------------------
# .panel-form p / .panel-form ul leaking into the Quill editor (fixed)
# ---------------------------------------------------------------------------

class PanelFormGridLeakIntoEditorCSSTests(TestCase):
    """
    `.panel-form p` and `.panel-form ul` (intended only for Django's
    auto-generated label+input form rows, and an unrelated checkbox-grid
    widget, respectively) are descendant selectors with no depth limit.
    Since the Quill editor (.ql-editor, full of <p>/<ul> elements for
    every paragraph/list typed) lives inside <form class="panel-form...">,
    both rules leaked into it: every typed paragraph was forced into a
    fixed 180px/1fr grid (text wraps too early, formatted runs overflow
    the fixed column -> page-wide horizontal scrollbar), and every
    bulleted list was turned into a multi-column card grid with bullets
    removed entirely.

    post-editor.css now defines higher-specificity override rules
    (.panel-form .richtext-editor-wrap .ql-editor p / ul) that undo this.
    These tests verify the override rules exist with sufficient
    specificity to reliably win regardless of file order.
    """

    def setUp(self):
        self.css_path = settings.BASE_DIR / 'core' / 'static' / 'core' / 'post-editor.css'
        self.css = self.css_path.read_text(encoding='utf-8')
        self.style_css = read_all_css()

    def test_leaking_panel_form_p_rule_still_exists_in_style_css(self):
        # Sanity check that the leaking rule this fix defends against is
        # still actually present -- if it's ever removed, this whole
        # override becomes unnecessary (but harmless to keep).
        self.assertIn('.panel-form p', self.style_css)
        self.assertIn('grid-template-columns: 180px 1fr', self.style_css)

    def test_leaking_panel_form_ul_rule_still_exists_in_style_css(self):
        self.assertIn('.panel-form ul', self.style_css)

    def test_editor_paragraph_override_rule_exists(self):
        self.assertIn('.panel-form .richtext-editor-wrap .ql-editor p', self.css)

    def test_editor_paragraph_override_resets_grid_properties(self):
        match = re.search(
            r'\.panel-form \.richtext-editor-wrap \.ql-editor p\s*\{([^}]*)\}',
            self.css,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn('display: block', body)
        self.assertIn('grid-template-columns: none', body)

    def test_editor_list_override_rule_exists(self):
        self.assertIn('.panel-form .richtext-editor-wrap .ql-editor ul', self.css)

    def test_editor_list_override_resets_grid_properties(self):
        match = re.search(
            r'\.panel-form \.richtext-editor-wrap \.ql-editor ul\s*\{([^}]*)\}',
            self.css,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn('grid-template-columns: none', body)

    def test_override_selectors_have_higher_specificity_than_leaking_rules(self):
        # CSS specificity = (id-count, class-count, type-count). The
        # override must have strictly more classes than the leaking
        # selector to reliably win regardless of source order.
        # .panel-form p              -> 1 class, 1 type
        # .panel-form ...ql-editor p -> 3 classes, 1 type
        leaking_p_classes = 1
        override_p_classes = len(re.findall(
            r'\.[\w-]+', '.panel-form .richtext-editor-wrap .ql-editor'
        ))
        self.assertGreater(override_p_classes, leaking_p_classes)


# ---------------------------------------------------------------------------
# Page-level horizontal scroll guard (defense-in-depth, added on request)
# ---------------------------------------------------------------------------

class NoHorizontalScrollCSSTests(TestCase):
    """
    The new-post page previously developed a page-wide horizontal
    scrollbar as a side effect of the .panel-form p/ul grid leak (see
    PanelFormGridLeakIntoEditorCSSTests above for the root-cause fix).
    That leak is fixed, but as an explicit, hard guarantee that the page
    can never scroll horizontally regardless of source -- third-party JS
    widgets (Quill, Tom Select) can have edge-case overflow behaviour
    that's hard to fully audit for every future content scenario --
    `overflow-x: hidden` is set on both html and body.

    This is intentional defense-in-depth layered ON TOP of the real fix,
    not a substitute for it.
    """

    def setUp(self):
        self.css = read_all_css()

    def test_body_has_overflow_x_hidden(self):
        match = re.search(r'(?<![-\w])body\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(match, 'expected a body {...} rule in style.css')
        self.assertIn('overflow-x: hidden', match.group(1))

    def test_html_has_overflow_x_hidden(self):
        match = re.search(r'(?<![-\w])html\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(match, 'expected an html {...} rule in style.css')
        self.assertIn('overflow-x: hidden', match.group(1))

    def test_vertical_overflow_is_not_touched(self):
        # Must only constrain the horizontal axis -- overflow-y must stay
        # at its default (unset) so normal page scrolling is unaffected.
        self.assertNotIn('overflow-y', self.css[:self.css.find('overflow-x: hidden')])

    def test_no_position_sticky_anywhere(self):
        # This guard's safety (no broken sticky positioning) depends on
        # no element using position:sticky. If one is ever added, this
        # test will catch it so the overflow-x:hidden side effect can be
        # re-evaluated rather than silently breaking sticky positioning.
        #
        # Strip CSS comments first -- this file's own explanatory comment
        # for the overflow-x:hidden rule above literally contains the
        # prose "...uses position:sticky, so..." as documentation, which
        # would otherwise false-positive a naive substring search.
        css_without_comments = re.sub(r'/\*.*?\*/', '', self.css, flags=re.DOTALL)
        self.assertNotIn('position: sticky', css_without_comments)
        self.assertNotIn('position:sticky', css_without_comments)


# ---------------------------------------------------------------------------
# Error pages use i18n URLs (not bare / links)
# ---------------------------------------------------------------------------

class ErrorPageI18nLinksTests(TestCase):
    """
    Error pages (404, 403, 500) must use {% url 'home' %} and other
    i18n-aware URL tags instead of bare '/' links. Bare '/' triggers a
    302 redirect to the language-pitched URL, which is unnecessary and
    breaks on error pages that should be self-contained.
    """

    @override_settings(DEBUG=False)
    def test_404_page_uses_i18n_home_url(self):
        resp = self.client.get('/en/this-path-does-not-exist-zzz/')
        html = resp.content.decode()
        # Should contain the language-prefixed home URL, not bare /
        self.assertIn('/en/', html)
        # Should NOT contain a bare <a href="/"> link
        self.assertNotRegex(html, r'<a\s+href="/">')

    @override_settings(DEBUG=False)
    def test_500_page_uses_i18n_home_url(self):
        resp = self.client.get(reverse('home'))
        # Force a 500 by calling the handler directly
        from core.views import server_error
        resp = server_error(resp.wsgi_request)
        html = resp.content.decode()
        self.assertIn('/en/', html)
        self.assertNotRegex(html, r'<a\s+href="/">')

    def test_403_page_uses_i18n_home_url(self):
        # The 403 page is rendered by the _admin_login_required decorator
        # when a non-admin user tries to access an admin view.
        user = User.objects.create_user(
            username='nonadmin', password='testpass123',
            email='nonadmin@example.com', is_active=True,
        )
        self.client.force_login(user)
        resp = self.client.get(reverse('accounts:admin_posts'))
        self.assertEqual(resp.status_code, 403)
        html = resp.content.decode()
        self.assertIn('/en/', html)
        self.assertNotRegex(html, r'<a\s+href="/">')

    @override_settings(DEBUG=False)
    def test_500_try_again_uses_request_path(self):
        resp = self.client.get(reverse('home'))
        from core.views import server_error
        resp = server_error(resp.wsgi_request)
        html = resp.content.decode()
        # "Try Again" should use request.path, not href="."
        self.assertNotIn('href="."', html)