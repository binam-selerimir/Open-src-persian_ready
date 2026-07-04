"""
core/middleware.py
====================
Custom middleware for cross-cutting, site-wide request/response concerns.
"""

from django.utils.csp import CSP

# Must match the prefix used in `path('admin/', admin.site.urls)` in
# myproject/urls.py. Kept as a constant here (rather than imported from
# urls.py, to avoid a circular import) -- if the admin is ever remounted
# at a different prefix, update both places.
ADMIN_URL_PREFIX = '/admin/'


class AdminCSPOverrideMiddleware:
    """
    Relaxes the Content-Security-Policy header for /admin/ requests only,
    adding 'unsafe-eval' to script-src so django-unfold's Alpine.js-powered
    UI (including its global search popup) can evaluate the inline
    x-data / x-on / x-show expressions it depends on.

    Background
    ----------
    This project's site-wide CSP (SECURE_CSP in settings.py) intentionally
    omits 'unsafe-eval' from script-src — the public site doesn't need it,
    and enabling it everywhere would meaningfully weaken XSS protection.
    However, django-unfold's admin UI is built on Alpine.js, which (in its
    default, non-CSP build) evaluates inline JS expressions written as
    plain strings in HTML attributes via `new Function(...)` under the
    hood — exactly what the 'unsafe-eval' CSP directive exists to block.

    Without 'unsafe-eval', Alpine's reactive UI pieces fail silently in
    the browser console with:
        EvalError: Refused to evaluate a string as JavaScript because
        'unsafe-eval' is not an allowed source of script...
    (See https://github.com/unfoldadmin/django-unfold/issues/1344 for the
    same symptom reported by another user, against an even less strict
    CSP than this project's own.)

    In practice this means the search popup still *opens* — Alpine's core
    runtime is a same-origin script, allowed under script-src 'self' — but
    never *closes*, because whatever closes it (e.g. an
    `x-on:click.outside="open = false"` or
    `x-on:keydown.escape="open = false"` binding) needs to evaluate that
    expression, which silently fails under a strict CSP.

    Rather than weakening the CSP for the entire site, this middleware
    swaps in a relaxed policy ONLY for requests under ADMIN_URL_PREFIX.
    The admin already requires authentication and `is_staff`, so the
    (still real, but now contained) 'unsafe-eval' trade-off only applies
    to authenticated staff sessions on admin pages, never to anonymous
    visitors on the public site.

    Security note
    -------------
    The 'unsafe-eval' directive is contained to admin-only pages, but it
    still weakens XSS protection for authenticated staff sessions. If an
    attacker achieves stored XSS in the admin panel (e.g., via a post body
    that bypasses sanitization), unsafe-eval enables arbitrary JavaScript
    execution. To eliminate this trade-off, consider using Alpine.js's
    CSP-compatible build (https://alpinejs.dev/essentials/installation#as-a-module)
    which uses `__l` instead of `new Function()`, removing the need for
    unsafe-eval. This requires coordination with django-unfold's Alpine.js
    usage.

    Mechanism
    ---------
    This works by setting the `_csp_config` attribute that Django's
    ContentSecurityPolicyMiddleware checks for on the response — the same
    attribute the built-in `@csp_override(...)` decorator sets (see
    django/views/decorators/csp.py). Per Django's docs, this fully
    REPLACES the policy for that response rather than merging with
    SECURE_CSP, so the dict below repeats every directive, not just
    script-src.

    Because ContentSecurityPolicyMiddleware only sees `_csp_config` if it
    has already been set on the response by the time its own
    response-phase code runs, this middleware MUST be listed in
    MIDDLEWARE *after* 'django.middleware.csp.ContentSecurityPolicyMiddleware'
    (Django's middleware response-phase runs bottom-to-top, so a
    middleware listed later runs its response-phase code first).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Use resolver_match instead of startswith so the override only
        # applies to the Django admin app namespace — future paths that
        # happen to start with '/admin/' (e.g. a public page) won't
        # accidentally inherit unsafe-eval.
        match = getattr(request, 'resolver_match', None)
        if match and getattr(match, 'app_name', '') == 'admin':
            response._csp_config = {
                "default-src": [CSP.SELF],
                "img-src": [CSP.SELF, "data:"],
                # 'unsafe-eval' is required for django-unfold's Alpine.js
                # UI to function correctly -- see the class docstring above.
                "script-src": [CSP.SELF, CSP.UNSAFE_EVAL],
                "style-src": [CSP.SELF],
                "font-src": [CSP.SELF],
                "frame-src": [CSP.NONE],
                "object-src": [CSP.NONE],
            }
        return response