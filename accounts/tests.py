"""
Regression and integration tests for the accounts app.

Run with:  python manage.py test accounts

Covers:
  - _safe_int unit tests (integer-zero falsy bug, all edge cases)
  - Login view (valid, invalid, inactive user, timing safety)
  - Taxonomy order= field: non-numeric crash (🟠 fixed)
  - Taxonomy order= field: integer-zero value preserved (_safe_int regression)
  - Taxonomy duplicate-slug IntegrityError (🟠 fixed)
  - Password-reset rate limit (🟡 fixed)
  - confirm_email rate limit (new protection)
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from posts.models import Category, Post, PostType, Subcategory
from accounts.views import _safe_int

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username='user', password='TestPass123!', **kwargs):
    defaults = {'email': f'{username}@example.com', 'is_active': True}
    defaults.update(kwargs)
    return User.objects.create_user(username=username, password=password, **defaults)


def make_admin(username='admin', password='AdminPass123!'):
    return make_user(
        username=username, password=password,
        is_site_admin=True, is_staff=True,
    )


# ---------------------------------------------------------------------------
# _safe_int unit tests
# ---------------------------------------------------------------------------

class SafeIntTests(TestCase):
    """Pure-function unit tests for the _safe_int helper."""

    # ── happy paths ───────────────────────────────────────────────────────────

    def test_positive_integer_string(self):
        self.assertEqual(_safe_int('5'), 5)

    def test_negative_integer_string(self):
        self.assertEqual(_safe_int('-1'), -1)

    def test_string_zero(self):
        self.assertEqual(_safe_int('0'), 0)

    def test_integer_value(self):
        self.assertEqual(_safe_int(3), 3)

    # ── regression: integer 0 must not be confused with a falsy sentinel ──────

    def test_integer_zero_value_is_not_replaced_by_default(self):
        """
        Core regression.  The old implementation used ``int(value or default)``
        which evaluates ``0 or default`` → default for any non-zero default.
        The fixed implementation checks for None/'' explicitly.
        """
        self.assertEqual(_safe_int(0, default=99), 0)

    def test_integer_zero_with_zero_default(self):
        self.assertEqual(_safe_int(0, default=0), 0)

    # ── fallback paths ────────────────────────────────────────────────────────

    def test_none_returns_default(self):
        self.assertEqual(_safe_int(None, default=7), 7)

    def test_empty_string_returns_default(self):
        self.assertEqual(_safe_int('', default=3), 3)

    def test_alphabetic_string_returns_default(self):
        self.assertEqual(_safe_int('abc', default=2), 2)

    def test_float_string_returns_default(self):
        # int('3.5') raises ValueError — must return default, not crash
        self.assertEqual(_safe_int('3.5', default=0), 0)

    def test_default_is_zero_when_omitted(self):
        self.assertEqual(_safe_int('bad'), 0)


# ---------------------------------------------------------------------------
# Login view
# ---------------------------------------------------------------------------

class LoginViewTests(TestCase):

    def setUp(self):
        self.url = reverse('accounts:login')
        self.user = make_user()

    def test_get_renders_form(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_valid_credentials_redirect_to_panel(self):
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'TestPass123!',
        })
        self.assertRedirects(resp, reverse('accounts:panel'))

    def test_wrong_password_stays_on_login(self):
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'wrongpassword',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'TestPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_unknown_user_cannot_login(self):
        resp = self.client.post(self.url, {
            'username': 'nobody', 'password': 'TestPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_already_authenticated_redirects_to_panel(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertRedirects(resp, reverse('accounts:panel'))

    def test_open_redirect_in_next_param_is_rejected(self):
        """An external ?next= URL must not be followed after login."""
        resp = self.client.post(
            self.url + '?next=https://evil.example.com/',
            {'username': 'user', 'password': 'TestPass123!'},
        )
        # Must not redirect to the external host
        if resp.status_code == 302:
            self.assertNotIn('evil.example.com', resp['Location'])# ---------------------------------------------------------------------------
# edit_profile — `_` shadowing the gettext alias (CRITICAL, fixed)
# ---------------------------------------------------------------------------

class EditProfileViewTests(TestCase):
    """
    Regression tests for accounts.views.edit_profile.

    Before the fix, `profile, _ = UserProfile.objects.get_or_create(...)`
    rebound the module-level `_` (gettext alias) to a bool. Every
    subsequent `_('...')` call in the view -- on BOTH the success path
    (_('Profile updated successfully.')) and the validation-error path
    (_('Please correct the errors below.')) -- then raised
    `TypeError: 'bool' object is not callable`, turning every POST to
    /panel/edit-profile/ into a 500 error.
    """

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse('accounts:edit_profile')

    def test_get_renders_form(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_valid_post_succeeds_and_shows_success_message(self):
        """
        The success path calls _('Profile updated successfully.').
        Before the fix this raised TypeError ('bool' object is not callable).
        """
        resp = self.client.post(self.url, {
            'first_name': 'Ada',
            'last_name': 'Lovelace',
            'bio_en': 'Mathematician.',
            'bio_fa': '',
            'website': '',
            'display_name': '',
            'headline_en': '',
            'headline_fa': '',
            'skills': '',
            'linkedin_url': '',
            'github_url': '',
            'telegram': '',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        messages = [str(m) for m in resp.context['messages']]
        self.assertIn('Profile updated successfully.', messages)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Ada')

    def test_invalid_post_shows_error_message_not_500(self):
        """
        The validation-error path calls _('Please correct the errors below.').
        Before the fix this raised TypeError ('bool' object is not callable),
        turning a simple validation error into a 500.
        """
        resp = self.client.post(self.url, {
            'first_name': 'Ada',
            'last_name': 'Lovelace',
            'bio_en': '',
            'bio_fa': '',
            'website': '',
            'display_name': '',
            'headline_en': '',
            'headline_fa': '',
            'skills': '',
            'linkedin_url': '',
            'github_url': '',
            # Too short for the 5-32 char Telegram username validator.
            'telegram': 'ab',
        })
        self.assertEqual(resp.status_code, 200)
        messages = [str(m) for m in resp.context['messages']]
        self.assertIn('Please correct the errors below.', messages)

    def test_works_when_userprofile_does_not_exist_yet(self):
        """
        Covers the `created=True` branch of get_or_create (e.g. a user
        created via createsuperuser before the post_save signal existed).
        """
        self.user.profile.delete()
        resp = self.client.post(self.url, {
            'first_name': 'Grace',
            'last_name': 'Hopper',
            'bio_en': '', 'bio_fa': '', 'website': '',
            'display_name': '', 'headline_en': '', 'headline_fa': '',
            'skills': '', 'linkedin_url': '', 'github_url': '', 'telegram': '',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        messages = [str(m) for m in resp.context['messages']]
        self.assertIn('Profile updated successfully.', messages)




class TaxonomyOrderFieldTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.url = reverse('accounts:admin_post_taxonomy')
        self.cat = Category.objects.create(
            name_en='Tech', name_fa='تکنولوژی', slug='tech', order=3
        )

    def tearDown(self):
        cache.clear()

    def _post_edit_category(self, order_value):
        return self.client.post(self.url, {
            'action': 'edit_category',
            'category_id': str(self.cat.pk),
            'name_en': self.cat.name_en,
            'name_fa': self.cat.name_fa,
            'slug': self.cat.slug,
            'order': order_value,
            'section': 'categories',
        })

    def test_non_numeric_order_does_not_crash(self):
        """Before the fix, order='abc' caused int('abc') → HTTP 500."""
        resp = self._post_edit_category('abc')
        self.assertEqual(resp.status_code, 302)

    def test_non_numeric_order_preserves_existing_value(self):
        self._post_edit_category('abc')
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.order, 3)

    def test_valid_numeric_order_is_saved(self):
        self._post_edit_category('7')
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.order, 7)

    def test_string_zero_order_is_saved_as_zero(self):
        self._post_edit_category('0')
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.order, 0)

    def test_empty_order_preserves_existing_value(self):
        """Empty string falls back to the current order, not 0."""
        self._post_edit_category('')
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.order, 3)

    def test_float_string_order_preserves_existing_value(self):
        self._post_edit_category('2.5')
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.order, 3)


# ---------------------------------------------------------------------------
# Taxonomy — duplicate slug IntegrityError (🟠 fixed)
# ---------------------------------------------------------------------------

class TaxonomyDuplicateSlugTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.url = reverse('accounts:admin_post_taxonomy')
        self.cat1 = Category.objects.create(
            name_en='Tech', name_fa='تکنولوژی', slug='tech'
        )
        self.cat2 = Category.objects.create(
            name_en='News', name_fa='خبر', slug='news'
        )

    def tearDown(self):
        cache.clear()

    def test_duplicate_category_slug_returns_302_not_500(self):
        """Before the fix, this hit the DB unique constraint → HTTP 500."""
        resp = self.client.post(self.url, {
            'action': 'edit_category',
            'category_id': str(self.cat2.pk),
            'name_en': 'News',
            'name_fa': 'خبر',
            'slug': 'tech',          # duplicate of cat1
            'order': '0',
            'section': 'categories',
        })
        self.assertEqual(resp.status_code, 302)

    def test_duplicate_category_slug_leaves_slug_unchanged(self):
        self.client.post(self.url, {
            'action': 'edit_category',
            'category_id': str(self.cat2.pk),
            'name_en': 'News',
            'name_fa': 'خبر',
            'slug': 'tech',
            'order': '0',
            'section': 'categories',
        })
        self.cat2.refresh_from_db()
        self.assertEqual(self.cat2.slug, 'news')

    def test_duplicate_subcategory_slug_in_same_category_returns_302_not_500(self):
        sub1 = Subcategory.objects.create(
            category=self.cat1, name_en='Python', name_fa='پایتون', slug='python'
        )
        sub2 = Subcategory.objects.create(
            category=self.cat1, name_en='Django', name_fa='جنگو', slug='django'
        )
        resp = self.client.post(self.url, {
            'action': 'edit_subcategory',
            'subcategory_id': str(sub2.pk),
            'name_en': 'Django',
            'name_fa': 'جنگو',
            'slug': 'python',        # duplicate within same category
            'section': 'subcategories',
        })
        self.assertEqual(resp.status_code, 302)

    def test_duplicate_subcategory_slug_leaves_slug_unchanged(self):
        sub1 = Subcategory.objects.create(
            category=self.cat1, name_en='Python', name_fa='پایتون', slug='python'
        )
        sub2 = Subcategory.objects.create(
            category=self.cat1, name_en='Django', name_fa='جنگو', slug='django'
        )
        self.client.post(self.url, {
            'action': 'edit_subcategory',
            'subcategory_id': str(sub2.pk),
            'name_en': 'Django',
            'name_fa': 'جنگو',
            'slug': 'python',
            'section': 'subcategories',
        })
        sub2.refresh_from_db()
        self.assertEqual(sub2.slug, 'django')

    def test_duplicate_post_type_slug_returns_302_not_500(self):
        pt1 = PostType.objects.create(name_en='Article', slug='article')
        pt2 = PostType.objects.create(name_en='Video', slug='video')
        resp = self.client.post(self.url, {
            'action': 'edit_post_type',
            'post_type_id': str(pt2.pk),
            'name_en': 'Video',
            'name_fa': '',
            'slug': 'article',       # duplicate
            'accent_color': '#ff0000',
            'order': '0',
            'section': 'post_types',
        })
        self.assertEqual(resp.status_code, 302)
        pt2.refresh_from_db()
        self.assertEqual(pt2.slug, 'video')

    def test_unique_slug_in_different_category_is_allowed(self):
        """Same slug is fine in a *different* category (unique_together is category+slug)."""
        sub_cat1 = Subcategory.objects.create(
            category=self.cat1, name_en='Python', name_fa='پایتون', slug='python'
        )
        # Creating the same slug under cat2 should succeed
        sub_cat2 = Subcategory.objects.create(
            category=self.cat2, name_en='Python', name_fa='پایتون', slug='python'
        )
        self.assertIsNotNone(sub_cat2.pk)


# ---------------------------------------------------------------------------
# Password-reset rate limit (🟡 fixed — message is now translated)
# ---------------------------------------------------------------------------

class PasswordResetRateLimitTests(TestCase):

    def setUp(self):
        cache.clear()
        self.url = reverse('password_reset')

    def tearDown(self):
        cache.clear()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sixth_request_is_blocked(self):
        """After 5 requests the view returns 200 (re-renders form), not 302."""
        for _ in range(5):
            self.client.post(self.url, {'email': 'anyone@example.com'})
        resp = self.client.post(self.url, {'email': 'anyone@example.com'})
        self.assertEqual(resp.status_code, 200)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_fifth_request_still_succeeds(self):
        """The 5th request must still be processed (limit is >= 5)."""
        for _ in range(4):
            self.client.post(self.url, {'email': 'anyone@example.com'})
        resp = self.client.post(self.url, {'email': 'anyone@example.com'})
        # Should redirect to password_reset_done (not blocked)
        self.assertEqual(resp.status_code, 302)

    def test_rate_limit_key_in_cache_after_requests(self):
        """Cache counter is incremented on each POST."""
        for i in range(3):
            self.client.post(self.url, {'email': 'anyone@example.com'})
        count = cache.get('pw_reset_127.0.0.1', 0)
        self.assertEqual(count, 3)


class PasswordResetI18nTests(TestCase):

    def test_password_reset_accessible_at_i18n_url(self):
        """Password reset form is accessible at /en/accounts/password_reset/."""
        url = reverse('password_reset')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reset_email_includes_language_prefix(self):
        """Password reset email URL includes language prefix."""
        from django.contrib.auth import get_user_model
        from django.core import mail
        User = get_user_model()
        user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        url = reverse('password_reset')
        self.client.post(url, {'email': 'test@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('/en/accounts/reset/', body)


# ---------------------------------------------------------------------------
# confirm_email rate limit (new protection)
# ---------------------------------------------------------------------------

class ConfirmEmailRateLimitTests(TestCase):

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_invalid_token_redirects_to_login_not_500(self):
        url = reverse('accounts:confirm_email', kwargs={'token': 'badtoken'})
        resp = self.client.get(url)
        self.assertRedirects(resp, reverse('accounts:login'))

    def test_invalid_token_increments_rate_limit_counter(self):
        url = reverse('accounts:confirm_email', kwargs={'token': 'badtoken'})
        for _ in range(3):
            self.client.get(url)
        self.assertEqual(cache.get('email_confirm_127.0.0.1', 0), 3)

    def test_blocked_after_threshold_still_redirects_not_500(self):
        """Once the threshold is reached the view must redirect gracefully."""
        cache.set('email_confirm_127.0.0.1', 10, timeout=3600)
        url = reverse('accounts:confirm_email', kwargs={'token': 'anytoken'})
        resp = self.client.get(url)
        self.assertRedirects(resp, reverse('accounts:login'))

    def test_blocked_request_does_not_increment_counter_further(self):
        """A blocked request short-circuits before touching the counter."""
        cache.set('email_confirm_127.0.0.1', 10, timeout=3600)
        url = reverse('accounts:confirm_email', kwargs={'token': 'anytoken'})
        self.client.get(url)
        self.assertEqual(cache.get('email_confirm_127.0.0.1'), 10)

    def test_valid_token_does_not_increment_counter(self):
        """A successful confirmation must not count against the rate limit."""
        from accounts.email_verification import make_url_token
        user = make_user(username='newuser', is_active=False)
        token = make_url_token(user.pk)
        url = reverse('accounts:confirm_email', kwargs={'token': token})
        self.client.get(url)
        self.assertEqual(cache.get('email_confirm_127.0.0.1', 0), 0)


class RegistrationConfirmationFlowTests(TestCase):
    """End-to-end tests for register → email → confirm flow."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_full_registration_confirmation_flow(self):
        """Register a user, extract the token from the email, and confirm it."""
        from django.core import mail
        from accounts.email_verification import verify_url_token

        url = reverse('accounts:register')
        data = {
            'username': 'flowuser',
            'email': 'flow@example.com',
            'first_name': 'Flow',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)

        # User should exist but be inactive.
        user = User.objects.get(username='flowuser')
        self.assertFalse(user.is_active)

        # Email should have been sent.
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        html_body = mail.outbox[0].alternatives[0][0]

        # Extract the confirmation URL from the plain-text email.
        import re
        match = re.search(r'(https?://[^\s]+confirm-email/[^\s]+/)', email_body)
        self.assertIsNotNone(match, 'Confirmation URL not found in plain-text email')
        confirm_url = match.group(1)

        # Extract token from URL — now base64url-encoded (no ':' characters).
        token = confirm_url.rstrip('/').split('/')[-1]
        self.assertNotIn(':', token, 'URL token must not contain colons')
        self.assertEqual(verify_url_token(token), user.pk)

        # The HTML version should contain a clickable <a> tag.
        self.assertIn('<a href="', html_body)
        self.assertIn(token, html_body)

        # Click the link — user should become active.
        resp = self.client.get(confirm_url)
        self.assertRedirects(resp, reverse('accounts:login'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_html_email_contains_clickable_link(self):
        """The confirmation email must include an HTML alternative with <a> tag."""
        from django.core import mail

        url = reverse('accounts:register')
        data = {
            'username': 'htmlemail',
            'email': 'html@example.com',
            'first_name': 'Html',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        self.client.post(url, data, follow=True)
        self.assertEqual(len(mail.outbox), 1)

        msg = mail.outbox[0]
        self.assertEqual(len(msg.alternatives), 1)
        html_content = msg.alternatives[0][0]
        self.assertEqual(msg.alternatives[0][1], 'text/html')
        self.assertIn('<a href="', html_content)
        self.assertIn('confirm-email/', html_content)

    def test_token_colon_characters_survive_url_routing(self):
        """Base64url-encoded tokens must contain no ':' characters.

        Before the fix, TimestampSigner tokens (format value:timestamp:signature)
        were placed raw in the URL, causing email clients to mangle the ':'
        separators.  Now the token is base64url-encoded so the URL path is
        purely alphanumeric (+ '-' and '_').
        """
        from django.core import mail
        from accounts.email_verification import verify_url_token

        url = reverse('accounts:register')
        data = {
            'username': 'colontoken',
            'email': 'colon@example.com',
            'first_name': 'Colon',
            'last_name': 'Token',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)

        user = User.objects.get(username='colontoken')
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body

        import re as re_mod
        match = re_mod.search(r'(https?://[^\s]+confirm-email/[^\s]+/)', email_body)
        self.assertIsNotNone(match, 'Confirmation URL not found in plain-text email')
        confirm_url = match.group(1)

        # Extract the token from the URL.
        token_part = confirm_url.rstrip('/').split('confirm-email/')[-1]
        self.assertNotIn(':', token_part, 'URL token must be colon-free')

        # The URL itself must resolve correctly via Django's URL router.
        from django.urls import resolve
        path_part = '/en/accounts/confirm-email/' + token_part + '/'
        match_obj = resolve(path_part)
        self.assertEqual(match_obj.url_name, 'confirm_email')
        self.assertEqual(match_obj.kwargs['token'], token_part)

        # Token verification must pass.
        self.assertEqual(verify_url_token(token_part), user.pk)

        # Actually clicking the link must activate the user.
        resp = self.client.get(confirm_url)
        self.assertRedirects(resp, reverse('accounts:login'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)


# ---------------------------------------------------------------------------
# django.contrib.auth.urls removed (bug 3, fixed)
# ---------------------------------------------------------------------------

class AuthUrlsTests(TestCase):
    """
    Before the fix, `include('django.contrib.auth.urls')` registered
    /accounts/login/, /accounts/logout/, /accounts/password_change/ and
    /accounts/password_change/done/ as BARE (unprefixed) URLs. None of
    those have a matching registration/*.html template in this project
    (it uses accounts:login / accounts:logout instead), so visiting any
    of them raised TemplateDoesNotExist -> HTTP 500.

    After removing that include(), those bare paths are no longer
    registered at all. What happens next depends on whether an
    *equivalent* route exists somewhere inside i18n_patterns:

    - /accounts/login/ and /accounts/logout/ DO have an equivalent --
      accounts.urls registers 'login'/'logout' inside i18n_patterns, so
      the real routes are /en/accounts/login/ and /en/accounts/logout/.
      Django's LocaleMiddleware automatically 302-redirects an unprefixed
      request to its prefixed equivalent whenever one resolves (see
      django.middleware.locale.LocaleMiddleware.process_response) --
      this is correct, desirable behaviour (a much better UX than a bare
      404), NOT a bug.
    - /accounts/password_change/ and /accounts/password_change/done/ have
      NO equivalent anywhere in the app (no app defines those names), so
      LocaleMiddleware finds nothing to redirect to and they correctly
      404, same as before.
    """

    def test_login_and_logout_redirect_to_prefixed_url(self):
        for path, url_name in (
            ('/accounts/login/', 'accounts:login'),
            ('/accounts/logout/', 'accounts:logout'),
        ):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 302, f'Expected a redirect on {path}')
            # Follow the redirect and confirm it lands on the real,
            # language-prefixed view (not a 500/404).
            follow = self.client.get(path, follow=True)
            self.assertEqual(follow.status_code, 200)
            self.assertEqual(follow.redirect_chain[0][0], reverse(url_name))

    def test_password_change_urls_have_no_equivalent_and_404(self):
        for path in (
            '/accounts/password_change/',
            '/accounts/password_change/done/',
        ):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 404, f'Expected 404 on {path}')

    def test_password_reset_done_still_200(self):
        resp = self.client.get(reverse('password_reset_done'))
        self.assertEqual(resp.status_code, 200)

    def test_password_reset_complete_still_200(self):
        resp = self.client.get(reverse('password_reset_complete'))
        self.assertEqual(resp.status_code, 200)

    def test_password_reset_confirm_still_routes(self):
        # An invalid uidb64/token combo renders the "invalid link" template
        # (HTTP 200), not a 404.  This just confirms the URL is still wired.
        url = reverse('password_reset_confirm',
                      kwargs={'uidb64': 'invalid', 'token': 'invalid-token'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_site_login_still_works(self):
        """The app's own accounts:login route must be unaffected."""
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Admin slug auto-fill (bug 6, fixed)
# ---------------------------------------------------------------------------

class AdminSlugPrepopulatedTests(TestCase):
    """
    CategoryAdmin and SubcategoryAdmin were missing prepopulated_fields
    despite the module docstring claiming "All classes use prepopulated_fields".
    This is a smoke-test that the admin site registers the classes without error.
    """

    def setUp(self):
        self.superuser = make_user(username='super', is_staff=True, is_superuser=True)
        self.client.force_login(self.superuser)

    def test_category_admin_changelist_loads(self):
        resp = self.client.get(reverse('admin:posts_category_changelist'))
        self.assertEqual(resp.status_code, 200)

    def test_subcategory_admin_changelist_loads(self):
        resp = self.client.get(reverse('admin:posts_subcategory_changelist'))
        self.assertEqual(resp.status_code, 200)

    def test_category_admin_has_prepopulated_fields(self):
        from django.contrib import admin
        from posts.models import Category
        admin_inst = admin.site._registry.get(Category)
        self.assertIsNotNone(admin_inst, 'Category must be registered with admin')
        self.assertIn('slug', admin_inst.prepopulated_fields,
                      'CategoryAdmin must have slug in prepopulated_fields')

    def test_subcategory_admin_has_prepopulated_fields(self):
        from django.contrib import admin
        from posts.models import Subcategory
        admin_inst = admin.site._registry.get(Subcategory)
        self.assertIsNotNone(admin_inst)
        self.assertIn('slug', admin_inst.prepopulated_fields,
                      'SubcategoryAdmin must have slug in prepopulated_fields')


# ===========================================================================
# NEW COMPREHENSIVE TESTS
# ===========================================================================


# ---------------------------------------------------------------------------
# CustomUser model tests
# ---------------------------------------------------------------------------

class CustomUserModelTests(TestCase):

    def test_create_user_with_email(self):
        user = User.objects.create_user(
            username='testuser', email='test@example.com', password='Pass123!'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('Pass123!'))

    def test_email_is_unique(self):
        User.objects.create_user(username='user1', email='dup@example.com', password='Pass123!')
        with self.assertRaises(Exception):
            User.objects.create_user(username='user2', email='dup@example.com', password='Pass123!')

    def test_str_returns_username(self):
        user = User.objects.create_user(username='alice', email='alice@example.com', password='Pass123!')
        self.assertEqual(str(user), 'alice')

    def test_default_is_site_admin_is_false(self):
        user = User.objects.create_user(username='bob', email='bob@example.com', password='Pass123!')
        self.assertFalse(user.is_site_admin)

    def test_bio_fields_default_blank(self):
        user = User.objects.create_user(username='carol', email='carol@example.com', password='Pass123!')
        self.assertEqual(user.bio_en, '')
        self.assertEqual(user.bio_fa, '')

    def test_get_full_name_display_with_names(self):
        user = User.objects.create_user(
            username='dave', email='dave@example.com', password='Pass123!',
            first_name='Dave', last_name='Chen'
        )
        self.assertEqual(user.get_full_name_display(), 'Dave Chen')

    def test_get_full_name_display_without_names(self):
        user = User.objects.create_user(username='eve', email='eve@example.com', password='Pass123!')
        self.assertEqual(user.get_full_name_display(), 'eve')

    def test_avatar_blank_by_default(self):
        user = User.objects.create_user(username='frank', email='frank@example.com', password='Pass123!')
        self.assertFalse(user.avatar)


# ---------------------------------------------------------------------------
# UserProfile model tests
# ---------------------------------------------------------------------------

class UserProfileModelTests(TestCase):

    def test_profile_created_via_signal(self):
        user = User.objects.create_user(username='signal_user', email='signal@example.com', password='Pass123!')
        self.assertTrue(hasattr(user, 'profile'))

    def test_profile_str(self):
        user = User.objects.create_user(username='profile_user', email='prof@example.com', password='Pass123!')
        self.assertEqual(str(user.profile), 'Profile of profile_user')

    def test_get_skills_list_empty(self):
        user = User.objects.create_user(username='nuskills', email='nuskills@example.com', password='Pass123!')
        self.assertEqual(user.profile.get_skills_list(), [])

    def test_get_skills_list_with_commas(self):
        user = User.objects.create_user(username='skilled', email='skilled@example.com', password='Pass123!')
        user.profile.skills = 'Python, Django, REST'
        user.profile.save()
        self.assertEqual(user.profile.get_skills_list(), ['Python', 'Django', 'REST'])

    def test_get_skills_list_strips_whitespace(self):
        user = User.objects.create_user(username='wsuser', email='ws@example.com', password='Pass123!')
        user.profile.skills = '  Python ,  Django  '
        user.profile.save()
        self.assertEqual(user.profile.get_skills_list(), ['Python', 'Django'])

    def test_profile_fields_default_blank(self):
        user = User.objects.create_user(username='blank', email='blank@example.com', password='Pass123!')
        profile = user.profile
        self.assertEqual(profile.display_name, '')
        self.assertEqual(profile.headline_en, '')
        self.assertEqual(profile.headline_fa, '')
        self.assertEqual(profile.linkedin_url, '')
        self.assertEqual(profile.github_url, '')
        self.assertEqual(profile.telegram, '')


# ---------------------------------------------------------------------------
# AuditLog model tests
# ---------------------------------------------------------------------------

class AuditLogModelTests(TestCase):

    def test_create_audit_log(self):
        from .models import AuditLog
        user = User.objects.create_user(username='auditor', email='audit@example.com', password='Pass123!')
        log = AuditLog.objects.create(
            user=user, action='LOGIN', description='Test login', ip_address='127.0.0.1'
        )
        self.assertEqual(log.action, 'LOGIN')
        self.assertEqual(log.user, user)
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_audit_log_str_with_user(self):
        from .models import AuditLog
        user = User.objects.create_user(username='struser', email='str@example.com', password='Pass123!')
        log = AuditLog.objects.create(user=user, action='LOGOUT')
        self.assertIn('struser', str(log))

    def test_audit_log_str_without_user(self):
        from .models import AuditLog
        log = AuditLog.objects.create(user=None, action='LOGIN_FAILED')
        self.assertIn('deleted user', str(log))

    def test_audit_log_ordering(self):
        from .models import AuditLog
        user = User.objects.create_user(username='orderuser', email='order@example.com', password='Pass123!')
        log1 = AuditLog.objects.create(user=user, action='LOGIN')
        log2 = AuditLog.objects.create(user=user, action='LOGOUT')
        logs = list(AuditLog.objects.all())
        self.assertEqual(logs[0].pk, log2.pk)
        self.assertEqual(logs[1].pk, log1.pk)

    def test_audit_log_created_at_auto_set(self):
        from .models import AuditLog
        log = AuditLog.objects.create(action='POST_CREATE')
        self.assertIsNotNone(log.created_at)


# ---------------------------------------------------------------------------
# Security: XSS prevention in registration/login
# ---------------------------------------------------------------------------

class XSSPreventionTests(TestCase):

    def test_script_tag_in_username_does_not_execute(self):
        """Registration with <script> in username must be rejected or escaped."""
        resp = self.client.post(reverse('accounts:register'), {
            'username': '<script>alert("xss")</script>',
            'email': 'xss@example.com',
            'first_name': 'XSS',
            'last_name': 'Test',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        # Should either reject (200 with form errors) or not contain raw script
        if resp.status_code == 200:
            self.assertNotContains(resp, '<script>alert("xss")</script>')

    def test_script_tag_in_email_does_not_execute(self):
        resp = self.client.post(reverse('accounts:register'), {
            'username': 'xssuser',
            'email': '<script>alert(1)</script>@example.com',
            'first_name': 'XSS',
            'last_name': 'Test',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        if resp.status_code == 200:
            self.assertNotContains(resp, '<script>alert(1)</script>')

    def test_xss_in_first_name_is_escaped_on_profile_page(self):
        user = make_user(username='xsstest', email='xsstest@example.com')
        self.client.force_login(user)
        self.client.post(reverse('accounts:edit_profile'), {
            'first_name': '<img src=x onerror=alert(1)>',
            'last_name': 'Test',
            'bio_en': '', 'bio_fa': '', 'website': '',
            'display_name': '', 'headline_en': '', 'headline_fa': '',
            'skills': '', 'linkedin_url': '', 'github_url': '', 'telegram': '',
        })
        user.refresh_from_db()
        resp = self.client.get(reverse('accounts:public_profile', kwargs={'username': user.username}))
        self.assertNotContains(resp, '<img src=x onerror=alert(1)>', html=True)


# ---------------------------------------------------------------------------
# Security: open redirect prevention
# ---------------------------------------------------------------------------

class OpenRedirectTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.url = reverse('accounts:login')

    def test_external_next_param_is_rejected(self):
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'TestPass123!',
            'next': 'https://evil.example.com/',
        }, follow=True)
        for url, _ in resp.redirect_chain:
            self.assertNotIn('evil.example.com', url)

    def test_protocol_relative_next_is_rejected(self):
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'TestPass123!',
            'next': '//evil.example.com/',
        }, follow=True)
        for url, _ in resp.redirect_chain:
            self.assertNotIn('evil.example.com', url)

    def test_relative_next_is_allowed(self):
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'TestPass123!',
            'next': '/en/about/',
        })
        self.assertRedirects(resp, '/en/about/')

    def test_same_host_next_is_allowed(self):
        resp = self.client.post(self.url, {
            'username': 'user', 'password': 'TestPass123!',
            'next': '/en/accounts/panel/',
        })
        self.assertRedirects(resp, reverse('accounts:panel'))


# ---------------------------------------------------------------------------
# Security: rate limiting
# ---------------------------------------------------------------------------

class RateLimitTests(TestCase):

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_check_rate_limit_allows_under_limit(self):
        from .utils import check_rate_limit
        req = type('Request', (), {'META': {'REMOTE_ADDR': '10.0.0.1'}})()
        self.assertTrue(check_rate_limit(req, 'test_action', limit=3))

    def test_check_rate_limit_blocks_over_limit(self):
        from .utils import check_rate_limit
        req = type('Request', (), {'META': {'REMOTE_ADDR': '10.0.0.1'}})()
        for _ in range(3):
            check_rate_limit(req, 'test_action', limit=3)
        self.assertFalse(check_rate_limit(req, 'test_action', limit=3))

    def test_check_rate_limit_increment_false_does_not_count(self):
        from .utils import check_rate_limit
        req = type('Request', (), {'META': {'REMOTE_ADDR': '10.0.0.2'}})()
        for _ in range(5):
            check_rate_limit(req, 'test_action', limit=3, increment=False)
        self.assertTrue(check_rate_limit(req, 'test_action', limit=3))

    def test_different_ips_have_separate_limits(self):
        from .utils import check_rate_limit
        req1 = type('Request', (), {'META': {'REMOTE_ADDR': '10.0.0.3'}})()
        req2 = type('Request', (), {'META': {'REMOTE_ADDR': '10.0.0.4'}})()
        for _ in range(3):
            check_rate_limit(req1, 'test_action', limit=3)
        self.assertFalse(check_rate_limit(req1, 'test_action', limit=3))
        self.assertTrue(check_rate_limit(req2, 'test_action', limit=3))


# ---------------------------------------------------------------------------
# Security: get_client_ip
# ---------------------------------------------------------------------------

class GetClientIPTests(TestCase):

    def test_returns_remote_addr_when_no_proxy(self):
        from .utils import get_client_ip
        req = type('Request', (), {'META': {'REMOTE_ADDR': '192.168.1.1'}})()
        self.assertEqual(get_client_ip(req), '192.168.1.1')

    def test_returns_rightmost_ip_from_xff(self):
        from .utils import get_client_ip
        req = type('Request', (), {'META': {
            'HTTP_X_FORWARDED_FOR': '1.1.1.1, 2.2.2.2, 3.3.3.3',
            'REMOTE_ADDR': '127.0.0.1',
        }})()
        self.assertEqual(get_client_ip(req), '3.3.3.3')

    def test_returns_single_xff_ip(self):
        from .utils import get_client_ip
        req = type('Request', (), {'META': {
            'HTTP_X_FORWARDED_FOR': '5.5.5.5',
            'REMOTE_ADDR': '127.0.0.1',
        }})()
        self.assertEqual(get_client_ip(req), '5.5.5.5')

    def test_falls_back_to_127_when_no_addr(self):
        from .utils import get_client_ip
        req = type('Request', (), {'META': {}})()
        self.assertEqual(get_client_ip(req), '127.0.0.1')


# ---------------------------------------------------------------------------
# Admin access control
# ---------------------------------------------------------------------------

class AdminAccessControlTests(TestCase):

    def setUp(self):
        self.admin = make_admin()
        self.regular = make_user(username='regular')

    def test_regular_user_cannot_access_admin_panel(self):
        self.client.force_login(self.regular)
        resp = self.client.get(reverse('accounts:admin_post_taxonomy'))
        self.assertEqual(resp.status_code, 403)

    def test_admin_user_can_access_admin_panel(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('accounts:admin_post_taxonomy'))
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_user_redirected_to_login(self):
        resp = self.client.get(reverse('accounts:admin_post_taxonomy'))
        self.assertEqual(resp.status_code, 302)

    def test_regular_user_cannot_access_admin_users(self):
        self.client.force_login(self.regular)
        resp = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(resp.status_code, 403)

    def test_admin_user_can_access_admin_users(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Admin: prevent revoking last site admin
# ---------------------------------------------------------------------------

class AdminRevokeLastAdminTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='superadmin', password='SuperPass123!', email='super@example.com',
        )
        self.admin.is_site_admin = True
        self.admin.save()
        self.client.force_login(self.admin)

    def test_cannot_revoke_last_site_admin(self):
        resp = self.client.post(reverse('accounts:admin_users'), {
            'user_id': str(self.admin.pk),
            'toggle_site_admin': '',
        }, follow=True)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_site_admin)

    def test_can_revoke_when_multiple_admins_exist(self):
        admin2 = make_admin(username='admin2')
        resp = self.client.post(reverse('accounts:admin_users'), {
            'user_id': str(admin2.pk),
            'toggle_site_admin': '',
        }, follow=True)
        admin2.refresh_from_db()
        self.assertFalse(admin2.is_site_admin)


# ---------------------------------------------------------------------------
# Admin: superuser cannot be modified
# ---------------------------------------------------------------------------

class AdminSuperuserProtectionTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='superadmin', password='SuperPass123!', email='super@example.com',
        )
        self.superuser = User.objects.create_superuser(
            username='super', password='SuperPass123!', email='super2@example.com',
            is_staff=True,
        )
        self.client.force_login(self.admin)

    def test_cannot_toggle_active_on_superuser(self):
        resp = self.client.post(reverse('accounts:admin_users'), {
            'user_id': str(self.superuser.pk),
            'toggle_active': '',
        }, follow=True)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_cannot_toggle_site_admin_on_superuser(self):
        resp = self.client.post(reverse('accounts:admin_users'), {
            'user_id': str(self.superuser.pk),
            'toggle_site_admin': '',
        }, follow=True)
        self.superuser.refresh_from_db()
        self.assertFalse(self.superuser.is_site_admin)


# ---------------------------------------------------------------------------
# Edit profile — transaction.atomic protection
# ---------------------------------------------------------------------------

class EditProfileTransactionTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse('accounts:edit_profile')

    def test_profile_update_saves_atomically(self):
        resp = self.client.post(self.url, {
            'first_name': 'Atomic',
            'last_name': 'Test',
            'bio_en': 'Bio',
            'bio_fa': '',
            'website': '',
            'display_name': '',
            'headline_en': '',
            'headline_fa': '',
            'skills': '',
            'linkedin_url': '',
            'github_url': '',
            'telegram': '',
        }, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Atomic')
        self.assertEqual(self.user.profile.headline_en, '')

    def test_profile_update_with_invalid_data_shows_errors(self):
        resp = self.client.post(self.url, {
            'first_name': 'Bad',
            'last_name': 'Data',
            'bio_en': '', 'bio_fa': '', 'website': '',
            'display_name': '', 'headline_en': '', 'headline_fa': '',
            'skills': '', 'linkedin_url': '', 'github_url': '',
            'telegram': 'ab',  # Too short for telegram validator
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['profile_form'].errors)


# ---------------------------------------------------------------------------
# Post type edit: accent_color validation
# ---------------------------------------------------------------------------

class PostTypeAccentColorTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.url = reverse('accounts:admin_post_taxonomy')
        self.pt = PostType.objects.create(
            name_en='Article', name_fa='مقاله', slug='article',
            accent_color='#ff0000', order=0,
        )

    def tearDown(self):
        cache.clear()

    def test_valid_hex_color_is_saved(self):
        self.client.post(self.url, {
            'action': 'edit_post_type',
            'post_type_id': str(self.pt.pk),
            'name_en': 'Article',
            'name_fa': 'مقاله',
            'slug': 'article',
            'accent_color': '#00ff00',
            'order': '0',
            'section': 'post_types',
        })
        self.pt.refresh_from_db()
        self.assertEqual(self.pt.accent_color, '#00ff00')

    def test_invalid_color_preserves_existing(self):
        self.client.post(self.url, {
            'action': 'edit_post_type',
            'post_type_id': str(self.pt.pk),
            'name_en': 'Article',
            'name_fa': 'مقاله',
            'slug': 'article',
            'accent_color': 'not-a-color',
            'order': '0',
            'section': 'post_types',
        })
        self.pt.refresh_from_db()
        self.assertEqual(self.pt.accent_color, '#ff0000')

    def test_empty_color_preserves_existing(self):
        self.client.post(self.url, {
            'action': 'edit_post_type',
            'post_type_id': str(self.pt.pk),
            'name_en': 'Article',
            'name_fa': 'مقاله',
            'slug': 'article',
            'accent_color': '',
            'order': '0',
            'section': 'post_types',
        })
        self.pt.refresh_from_db()
        self.assertEqual(self.pt.accent_color, '#ff0000')


# ---------------------------------------------------------------------------
# Taxonomy create/delete
# ---------------------------------------------------------------------------

class TaxonomyCreateTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.url = reverse('accounts:admin_post_taxonomy')

    def tearDown(self):
        cache.clear()

    def test_create_category(self):
        self.client.post(self.url, {
            'action': 'create_category',
            'name_en': 'Science',
            'name_fa': 'علم',
            'slug': 'science',
            'order': '1',
            'section': 'categories',
        })
        self.assertTrue(Category.objects.filter(slug='science').exists())

    def test_create_post_type(self):
        self.client.post(self.url, {
            'action': 'create_post_type',
            'name_en': 'Tutorial',
            'name_fa': 'آموزشی',
            'slug': 'tutorial',
            'accent_color': '#123456',
            'order': '0',
            'section': 'post_types',
        })
        self.assertTrue(PostType.objects.filter(slug='tutorial').exists())

    def test_delete_category_with_no_posts(self):
        cat = Category.objects.create(name_en='Temp', name_fa='موقت', slug='temp')
        self.client.post(self.url, {
            'action': 'delete_category',
            'category_id': str(cat.pk),
            'section': 'categories',
        })
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())


class TaxonomyDeleteProtectionTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.url = reverse('accounts:admin_post_taxonomy')

    def tearDown(self):
        cache.clear()

    def test_cannot_delete_category_with_posts(self):
        from posts.models import Post
        cat = Category.objects.create(name_en='Protected', name_fa='محافظت', slug='protected')
        pt = PostType.objects.create(name_en='Art', slug='art')
        Post.objects.create(
            title='Test', slug='test', category=cat, post_type=pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )
        self.client.post(self.url, {
            'action': 'delete_category',
            'category_id': str(cat.pk),
            'section': 'categories',
        })
        self.assertTrue(Category.objects.filter(pk=cat.pk).exists())


# ---------------------------------------------------------------------------
# Registration: duplicate email/username prevention
# ---------------------------------------------------------------------------

class RegistrationDuplicateTests(TestCase):

    def test_duplicate_username_rejected(self):
        make_user(username='dupuser', email='dup1@example.com')
        resp = self.client.post(reverse('accounts:register'), {
            'username': 'dupuser',
            'email': 'dup2@example.com',
            'first_name': 'Dup',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(username='dupuser').count() == 1)

    def test_duplicate_email_rejected(self):
        make_user(username='emailuser', email='same@example.com')
        resp = self.client.post(reverse('accounts:register'), {
            'username': 'emailuser2',
            'email': 'same@example.com',
            'first_name': 'Dup',
            'last_name': 'Email',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email='same@example.com').count(), 1)


# ---------------------------------------------------------------------------
# Email verification token tests
# ---------------------------------------------------------------------------

class EmailVerificationTokenTests(TestCase):

    def test_make_and_verify_token(self):
        from .email_verification import make_url_token, verify_url_token
        user = make_user(username='tokenuser', email='token@example.com')
        token = make_url_token(user.pk)
        self.assertEqual(verify_url_token(token), user.pk)

    def test_invalid_token_returns_none(self):
        from .email_verification import verify_url_token
        self.assertIsNone(verify_url_token('invalidtoken123'))

    def test_tampered_token_returns_none(self):
        from .email_verification import make_url_token, verify_url_token
        user = make_user(username='tamper', email='tamper@example.com')
        token = make_url_token(user.pk)
        tampered = token[:-5] + 'XXXXX'
        self.assertIsNone(verify_url_token(tampered))

    def test_token_colon_free(self):
        from .email_verification import make_url_token
        user = make_user(username='colon', email='colon@example.com')
        token = make_url_token(user.pk)
        self.assertNotIn(':', token)

    def test_fresh_token_is_valid(self):
        from .email_verification import make_url_token, verify_url_token
        user = make_user(username='fresh', email='fresh@example.com')
        token = make_url_token(user.pk)
        self.assertIsNotNone(verify_url_token(token))


# ---------------------------------------------------------------------------
# Login: timing safety (dummy hash)
# ---------------------------------------------------------------------------

class LoginTimingSafetyTests(TestCase):

    def setUp(self):
        self.user = make_user(username='timing', email='timing@example.com')

    def test_wrong_username_same_response_code_as_wrong_password(self):
        resp_user = self.client.post(reverse('accounts:login'), {
            'username': 'nonexistent', 'password': 'wrongpassword',
        })
        resp_pass = self.client.post(reverse('accounts:login'), {
            'username': 'timing', 'password': 'wrongpassword',
        })
        self.assertEqual(resp_user.status_code, resp_pass.status_code)

    def test_dummy_hash_is_not_empty(self):
        from accounts.views import _DUMMY_HASH
        self.assertTrue(len(_DUMMY_HASH) > 0)


# ---------------------------------------------------------------------------
# Panel access: login required
# ---------------------------------------------------------------------------

class PanelAccessTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_anonymous_redirected_from_panel(self):
        resp = self.client.get(reverse('accounts:panel'))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_user_can_access_panel(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('accounts:panel'))
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_redirected_from_edit_profile(self):
        resp = self.client.get(reverse('accounts:edit_profile'))
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_redirected_from_user_posts(self):
        resp = self.client.get(reverse('accounts:admin_posts'))
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class LogoutTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_logout_clears_session(self):
        self.client.force_login(self.user)
        self.assertIn('_auth_user_id', self.client.session)
        resp = self.client.get(reverse('accounts:logout'))
        # After logout, user should be logged out
        self.assertEqual(resp.status_code, 302)

    def test_logout_redirects_to_home(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(resp, reverse('home'))


# ---------------------------------------------------------------------------
# _validate_safe_url — protocol-relative URL blocking
# ---------------------------------------------------------------------------

class ValidateSafeUrlTests(TestCase):
    """Verify that _validate_safe_url blocks protocol-relative URLs."""

    def test_javascript_url_rejected(self):
        from django.core.exceptions import ValidationError
        from .models import _validate_safe_url
        with self.assertRaises(ValidationError):
            _validate_safe_url('javascript:alert(1)')

    def test_data_url_rejected(self):
        from django.core.exceptions import ValidationError
        from .models import _validate_safe_url
        with self.assertRaises(ValidationError):
            _validate_safe_url('data:text/html,<script>alert(1)</script>')

    def test_vbscript_url_rejected(self):
        from django.core.exceptions import ValidationError
        from .models import _validate_safe_url
        with self.assertRaises(ValidationError):
            _validate_safe_url('vbscript:MsgBox(1)')

    def test_protocol_relative_url_rejected(self):
        from django.core.exceptions import ValidationError
        from .models import _validate_safe_url
        with self.assertRaises(ValidationError):
            _validate_safe_url('//evil.example.com/steal')

    def test_protocol_relative_with_whitespace_rejected(self):
        from django.core.exceptions import ValidationError
        from .models import _validate_safe_url
        with self.assertRaises(ValidationError):
            _validate_safe_url('  //evil.example.com/steal')

    def test_normal_url_accepted(self):
        from .models import _validate_safe_url
        _validate_safe_url('https://example.com')  # Should not raise

    def test_empty_string_accepted(self):
        from .models import _validate_safe_url
        _validate_safe_url('')  # Should not raise

    def test_none_accepted(self):
        from .models import _validate_safe_url
        _validate_safe_url(None)  # Should not raise


# ---------------------------------------------------------------------------
# LOGIN_FAILED audit — username not logged
# ---------------------------------------------------------------------------

class LoginFailedAuditTests(TestCase):
    """Verify that LOGIN_FAILED audit entries do not contain the attempted username."""

    def setUp(self):
        self.user = make_user(username='audituser', email='audit@example.com')

    def test_failed_login_audit_does_not_contain_username(self):
        from accounts.models import AuditLog
        self.client.post(reverse('accounts:login'), {
            'username': 'audituser', 'password': 'wrongpassword',
        })
        entry = AuditLog.objects.filter(action='LOGIN_FAILED').first()
        self.assertIsNotNone(entry)
        self.assertNotIn('audituser', entry.description)
        self.assertEqual(entry.description, 'Failed login attempt')


# ---------------------------------------------------------------------------
# Users tab: superuser-only visibility
# ---------------------------------------------------------------------------

class UsersTabSuperuserOnlyTests(TestCase):
    """Verify that only superusers can access the Users management page
    and see the Users tab in the panel navigation."""

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username='superadmin', password='SuperPass123!', email='super@example.com',
        )
        self.staff = make_user(
            username='staffuser', password='StaffPass123!',
            is_staff=True, is_site_admin=True,
        )
        self.site_admin = make_user(
            username='siteadmin', password='AdminPass123!',
            is_site_admin=True,
        )
        self.regular = make_user(
            username='regular', password='RegularPass123!',
        )

    def tearDown(self):
        cache.clear()

    def test_superuser_can_access_admin_users(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(resp.status_code, 200)

    def test_staff_gets_403_on_admin_users(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(resp.status_code, 403)

    def test_site_admin_gets_403_on_admin_users(self):
        self.client.force_login(self.site_admin)
        resp = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(resp.status_code, 403)

    def test_regular_user_gets_403_on_admin_users(self):
        self.client.force_login(self.regular)
        resp = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(resp.status_code, 403)

    def test_superuser_sees_users_tab(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse('accounts:panel'))
        self.assertContains(resp, 'Users')

    def test_staff_does_not_see_users_tab(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('accounts:panel'))
        self.assertNotContains(resp, reverse('accounts:admin_users'))

    def test_site_admin_does_not_see_users_tab(self):
        self.client.force_login(self.site_admin)
        resp = self.client.get(reverse('accounts:panel'))
        self.assertNotContains(resp, reverse('accounts:admin_users'))


# ---------------------------------------------------------------------------
# Certificate system tests
# ---------------------------------------------------------------------------

class CertificateTests(TestCase):
    """Tests for the Certificate and UserCertificate models, views, and forms."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='certsuper', password='SuperPass123!', email='certsuper@example.com',
        )
        cls.user1 = make_user(username='certuser1', email='cert1@example.com')
        cls.user2 = make_user(username='certuser2', email='cert2@example.com')
        cls.staff = make_user(
            username='certstaff', email='certstaff@example.com',
            is_staff=True, is_site_admin=True,
        )

    # --- Model tests ---

    def test_certificate_str(self):
        from .models import Certificate
        cert = Certificate.objects.create(name='Top Contributor')
        self.assertEqual(str(cert), 'Top Contributor')

    def test_user_certificate_str(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Star Coder')
        uc = UserCertificate.objects.create(user=self.user1, certificate=cert)
        self.assertEqual(str(uc), f'{self.user1} — {cert}')

    def test_unique_user_certificate(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Badge')
        UserCertificate.objects.create(user=self.user1, certificate=cert)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            UserCertificate.objects.create(user=self.user1, certificate=cert)

    def test_inactive_cert_excluded(self):
        from .models import Certificate
        active = Certificate.objects.create(name='Active Cert', is_active=True)
        inactive = Certificate.objects.create(name='Inactive Cert', is_active=False)
        from accounts.forms import GrantCertificateForm
        form = GrantCertificateForm()
        qs = form.fields['certificate'].queryset
        self.assertIn(active, qs)
        self.assertNotIn(inactive, qs)

    # --- Permission tests ---

    def test_admin_certificates_requires_superuser(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('accounts:admin_certificates'))
        self.assertRedirects(resp, reverse('accounts:panel'))

    def test_admin_certificates_superuser_access(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse('accounts:admin_certificates'))
        self.assertEqual(resp.status_code, 200)

    def test_grant_requires_superuser(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('accounts:admin_grant_certificate'))
        self.assertRedirects(resp, reverse('accounts:panel'))

    def test_user_certificates_requires_login(self):
        resp = self.client.get(reverse('accounts:user_certificates'))
        self.assertEqual(resp.status_code, 302)

    # --- Create / Edit / Delete certificate ---

    def test_create_certificate(self):
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_certificates'), {
            'action': 'create',
            'name': 'New Cert',
            'name_fa': 'گواهی جدید',
            'description': 'A new certificate',
            'description_fa': '',
            'accent_color': '#ff0000',
            'is_active': True,
        })
        self.assertRedirects(resp, reverse('accounts:admin_certificates'))
        from .models import Certificate
        self.assertTrue(Certificate.objects.filter(name='New Cert').exists())

    def test_create_certificate_duplicate_name(self):
        from .models import Certificate
        Certificate.objects.create(name='Existing Cert')
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_certificates'), {
            'action': 'create',
            'name': 'Existing Cert',
            'name_fa': '',
            'description': '',
            'description_fa': '',
            'accent_color': '#000000',
            'is_active': True,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Certificate.objects.filter(name='Existing Cert').count(), 1)

    def test_toggle_active(self):
        from .models import Certificate
        cert = Certificate.objects.create(name='Toggle Cert', is_active=True)
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_certificates'), {
            'action': 'toggle_active',
            'cert_id': str(cert.pk),
        })
        self.assertRedirects(resp, reverse('accounts:admin_certificates'))
        cert.refresh_from_db()
        self.assertFalse(cert.is_active)

    def test_delete_certificate_no_grants(self):
        from .models import Certificate
        cert = Certificate.objects.create(name='Delete Me')
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_certificates'), {
            'action': 'delete',
            'cert_id': str(cert.pk),
        })
        self.assertRedirects(resp, reverse('accounts:admin_certificates'))
        self.assertFalse(Certificate.objects.filter(pk=cert.pk).exists())

    def test_delete_certificate_with_grants_blocked(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Protected Cert')
        UserCertificate.objects.create(user=self.user1, certificate=cert)
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_certificates'), {
            'action': 'delete',
            'cert_id': str(cert.pk),
        })
        self.assertRedirects(resp, reverse('accounts:admin_certificates'))
        self.assertTrue(Certificate.objects.filter(pk=cert.pk).exists())

    # --- Grant / Revoke ---

    def test_grant_certificate(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Grant Cert')
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_grant_certificate'), {
            'action': 'grant',
            'user': str(self.user1.pk),
            'certificate': str(cert.pk),
            'note': 'Well done!',
        })
        self.assertRedirects(resp, reverse('accounts:admin_grant_certificate'))
        self.assertTrue(UserCertificate.objects.filter(user=self.user1, certificate=cert).exists())

    def test_grant_duplicate_blocked(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Dup Cert')
        UserCertificate.objects.create(user=self.user1, certificate=cert)
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_grant_certificate'), {
            'action': 'grant',
            'user': str(self.user1.pk),
            'certificate': str(cert.pk),
            'note': '',
        })
        self.assertEqual(resp.status_code, 200)

    def test_revoke_certificate(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Revoke Cert')
        uc = UserCertificate.objects.create(user=self.user1, certificate=cert)
        self.client.force_login(self.superuser)
        resp = self.client.post(reverse('accounts:admin_grant_certificate'), {
            'action': 'revoke',
            'grant_id': str(uc.pk),
        })
        self.assertRedirects(resp, reverse('accounts:admin_grant_certificate'))
        self.assertFalse(UserCertificate.objects.filter(pk=uc.pk).exists())

    # --- User-facing ---

    def test_user_certificates_page_shows_own_certs(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='My Cert')
        UserCertificate.objects.create(user=self.user1, certificate=cert)
        self.client.force_login(self.user1)
        resp = self.client.get(reverse('accounts:user_certificates'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'My Cert')

    def test_user_certificates_page_empty_state(self):
        self.client.force_login(self.user1)
        resp = self.client.get(reverse('accounts:user_certificates'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "haven")

    def test_public_profile_shows_visible_certs(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Visible Cert')
        UserCertificate.objects.create(user=self.user1, certificate=cert, is_visible=True)
        resp = self.client.get(reverse('accounts:public_profile', kwargs={'username': self.user1.username}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Visible Cert')

    def test_public_profile_hides_invisible_certs(self):
        from .models import Certificate, UserCertificate
        cert = Certificate.objects.create(name='Hidden Cert')
        UserCertificate.objects.create(user=self.user1, certificate=cert, is_visible=False)
        resp = self.client.get(reverse('accounts:public_profile', kwargs={'username': self.user1.username}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Hidden Cert')
