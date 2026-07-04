"""
myproject/urls.py
=================
Root URL configuration for the OpenSrcPersian Django application.

URL structure
-------------
/admin/                      – Django admin panel (Unfold-themed).
/i18n/                       – Django language-switching endpoint
                               (set_language view used by the language toggle).
/accounts/password_reset/    – Rate-limited password-reset form (custom wrapper).
/accounts/password_reset/done/, /accounts/reset/<uidb64>/<token>/,
/accounts/reset/done/        – Remaining steps of Django's built-in
                               password-reset flow (the only parts of
                               django.contrib.auth.urls this project uses;
                               login/logout/password_change have no
                               templates here and are handled by the
                               accounts app instead, see /<lang>/accounts/).

All of the following are wrapped in i18n_patterns() so they gain a language-
code prefix (e.g. /en/posts/, /fa/posts/).  prefix_default_language=True means
/en/ is explicit even for English.

/<lang>/                     – Homepage and flat page views (core app).
/<lang>/posts/               – Post list, detail, category, subcategory views.
/<lang>/accounts/            – Login, register, email confirm, user panel.
/<lang>/search/              – Full-text search.

Custom error handlers
---------------------
handler404 is pointed at core.views.page_not_found so 404 pages use the
site's base layout with navigation intact.

Rate limiting
-------------
_RateLimitedPasswordResetView wraps Django's built-in PasswordResetView with
an IP-based rate limit (5 requests / IP / hour) to prevent email-flood abuse.
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib import messages as _messages
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from accounts.utils import check_rate_limit, audit
from core import views as core_views
from posts.sitemaps import CategorySitemap, PostSitemap

# Register the custom 404 handler (renders 404.html with the site layout).
handler404 = core_views.page_not_found
# Register the custom 500 handler (renders 500.html with the site layout).
handler500 = core_views.server_error


class _RateLimitedPasswordResetView(auth_views.PasswordResetView):
    """
    Wraps Django's built-in PasswordResetView with a simple IP-based rate
    limit (5 requests per hour) to prevent email-flood abuse.
    """

    def post(self, request, *args, **kwargs):
        if not check_rate_limit(request, 'pw_reset', limit=5):
            _messages.error(
                request,
                _(
                    'Too many password-reset requests from your IP address. '
                    'Please try again in an hour.'
                ),
            )
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)


class _SessionInvalidatingPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """
    Overrides Django's built-in PasswordResetConfirmView to flush the session
    after a successful password reset.

    Django's default token generator includes the user's password hash in the
    token signature, so the token is automatically invalidated when the password
    changes. However, any existing session cookies remain valid. This override
    flushes the session after setting the new password, forcing re-authentication
    and preventing session fixation via password reset.

    Fixes FINDING-02: Password reset sessions not invalidated.
    """

    def form_valid(self, form):
        response = super().form_valid(form)
        # Flush the session to invalidate any pre-reset session data.
        # This ensures that if an attacker had a valid session before the
        # password reset, it is now invalid.
        self.request.session.flush()
        audit(self.request, "PASSWORD_RESET", "Password reset completed — session flushed")
        return response


urlpatterns = [
    path('admin/', admin.site.urls),
    # Django's built-in language switcher — used by the language toggle button.
    path('i18n/', include('django.conf.urls.i18n')),
    # Sitemap — registered at /sitemap.xml for all search engines.
    path('sitemap.xml', sitemap, {
        'sitemaps': {
            'posts': PostSitemap,
            'categories': CategorySitemap,
        }
    }, name='django.contrib.sitemaps.views.sitemap'),
    # robots.txt — served as plain text from a template.
    path('robots.txt',
         TemplateView.as_view(template_name='robots.txt', content_type='text/plain'),
         name='robots'),
    # security.txt — responsible disclosure policy (RFC 9116).
    path('.well-known/security.txt',
         TemplateView.as_view(template_name='security.txt', content_type='text/plain'),
         name='security_txt'),
]

# All site URLs are wrapped in i18n_patterns to add the language prefix.
# prefix_default_language=True → /en/posts/ (not /posts/).
urlpatterns += i18n_patterns(
    path('', include('core.urls')),

    path('posts/', include('posts.urls', namespace='posts')),
    path('comments/', include('comments.urls', namespace='comments')),

    # Rate-limited password reset — inside i18n so email links include the
    # language prefix (e.g. /en/accounts/reset/...).
    path('accounts/password_reset/', _RateLimitedPasswordResetView.as_view(),
         name='password_reset'),
    # Only the parts of django.contrib.auth.urls that this project actually
    # uses and has templates for (password_reset_done, confirm, complete).
    # NOTE: do not `include('django.contrib.auth.urls')` wholesale -- it also
    # registers login/, logout/, password_change/ and password_change/done/,
    # none of which have a registration/*.html template in this project (the
    # site uses accounts:login / accounts:logout instead), so hitting those
    # URLs would raise TemplateDoesNotExist (500).
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', _SessionInvalidatingPasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),

    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('search/', include('search.urls', namespace='search')),
    path('forum/', include('forum.urls', namespace='forum')),
    prefix_default_language=True,
)

# In development, serve uploaded media files directly from Django.
# In production this is handled by Nginx (or the object storage).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
