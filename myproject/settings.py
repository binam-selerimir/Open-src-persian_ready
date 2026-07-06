"""
myproject/settings.py
=====================
Central Django configuration for the OpenSrcPersian platform.

All environment-specific secrets and toggles (SECRET_KEY, DEBUG,
ALLOWED_HOSTS, DATABASE_URL, email credentials, …) are read from
environment variables (or a .env file) via python-decouple so that
the same codebase can run unchanged in development and production
without any checked-in credentials.

Security design summary
-----------------------
* DEBUG=True → SQLite + console email + relaxed security headers.
* DEBUG=False → all production hardening applied (HSTS, HTTPS redirect,
  secure cookies, CSP, X-Frame-Options: DENY, …).  Raising RuntimeError
  if SECRET_KEY is still the default insecure value prevents an
  accidental production deployment with an unsafe key.

Key third-party integrations
----------------------------
* axes          – brute-force login protection (IP + username lockout).
* whitenoise    – self-hosted static file serving without an Nginx proxy.
* unfold        – modern admin theme replacing the default Django admin UI.
* dj-database-url – optional: switch backend via DATABASE_URL env var
                    (MySQL via mysqlclient is the production target).
* Content-Security-Policy – handled by Django 6.0's built-in
                    django.middleware.csp.ContentSecurityPolicyMiddleware
                    + the SECURE_CSP setting (no third-party app needed).
"""

from pathlib import Path

from decouple import Csv, config
from datetime import timedelta
from django.utils.csp import CSP
import sys
import pymysql
pymysql.install_as_MySQLdb()
config = Config(RepositoryEnv(str(Path(__file__).resolve().parent / '.env')))
# ---------------------------------------------------------------------------
# Runtime detection — must be defined before CACHE and STORAGES sections below
# ---------------------------------------------------------------------------
_RUNNING_TESTS = (
    'test' in sys.argv
    or 'pytest' in sys.modules
    or any('pytest' in arg for arg in sys.argv)
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Build paths inside the project like: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY:
    raise RuntimeError(
        'SECRET_KEY must be set via environment variable. '
        'Generate one with: python -c "from django.core.management.utils import '
        'get_random_secret_key; print(get_random_secret_key())"'
    )
# SECURITY: Default to False in production. Set DEBUG=True in .env for local dev.
DEBUG = config('DEBUG', default=False, cast=bool)

# Comma-separated list of host/domain names that this Django site can serve.
# Read from the environment so deployments don't need to touch code.
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Refuse to start in production with a wildcard ALLOWED_HOSTS (Host header attacks).
if not DEBUG and '*' in ALLOWED_HOSTS:
    raise RuntimeError(
        'ALLOWED_HOSTS must not contain "*" in production. '
        'Set explicit domain names via the ALLOWED_HOSTS environment variable.'
    )

# Comma-separated list of origins allowed to send cross-site requests
# (required for HTTPS deployments so CSRF middleware does not reject
# requests arriving over a proxy that rewrites the scheme).
# IMPORTANT: In production behind a reverse proxy, you MUST set this to your
# domain(s) e.g. "https://example.com,https://www.example.com" or all
# CSRF-protected POST requests (login, register, password reset) will fail.
CSRF_TRUSTED_ORIGINS = [
    o for o in config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv()) if o
]

# ---------------------------------------------------------------------------
# Cookie security (apply in all modes; production adds HTTPS-only via Secure flag)
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True       # Prevent JavaScript from accessing the session cookie.
CSRF_COOKIE_HTTPONLY = True          # Prevent JavaScript from reading the CSRF cookie.
SESSION_COOKIE_SAMESITE = 'Lax'     # CSRF mitigation for top-level navigations.
CSRF_COOKIE_SAMESITE = 'Lax'        # CSRF mitigation for top-level navigations.
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-type sniffing in all modes.

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # django-axes must come BEFORE django.contrib.admin so its auth backend
    # intercepts the admin login form and counts failed attempts.
    'axes',
    # Unfold replaces the default Django admin theme; must precede admin.
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    # Local apps – each encapsulates a distinct feature domain.
    'core',       # homepage, static pages, base templates
    'posts',      # articles, categories, tags, post types
    'accounts',   # custom user model, auth views, admin panel, audit log
    'search',     # full-text search across posts
    'comments',   # user comments with admin approval
    'forum',      # community forum — boards, threads, posts
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise serves compressed static files directly from Django;
    # must come immediately after SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # LocaleMiddleware activates translations based on Accept-Language /
    # URL prefix; must come after SessionMiddleware, before CommonMiddleware.
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # AxesMiddleware enforces lockout after too many failed login attempts.
    # Must come after AuthenticationMiddleware.
    'axes.middleware.AxesMiddleware',
    # ContentSecurityPolicyMiddleware (built into Django 6.0) appends the
    # Content-Security-Policy response header, configured via SECURE_CSP below.
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    # Relaxes CSP (adds 'unsafe-eval' to script-src) for /admin/ requests
    # only, so django-unfold's Alpine.js-based UI -- including its global
    # search popup -- can actually close. Must come AFTER
    # ContentSecurityPolicyMiddleware (see core/middleware.py docstring for
    # why the order matters, and for the full root-cause explanation).
    'core.middleware.AdminCSPOverrideMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],                 # App templates are discovered via APP_DIRS.
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Exposes LANGUAGE_CODE and other i18n data to templates.
                'django.template.context_processors.i18n',
                # Injects categories, latest_posts, and nav_pages into every
                # template — see core/context_processors.py.
                'core.context_processors.global_context',
                # Injects the active site alert banner into every template.
                'core.context_processors.site_alert',
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Reads DATABASE_URL from the environment when set. The project targets
# MySQL 8.0.11+ / MariaDB 10.6+ (Django 6's supported minimums) in
# production, but any dj-database-url-supported backend works.
# Falls back to SQLite for local development when DATABASE_URL is unset.
#
# Example production env var (MySQL):
#   DATABASE_URL=mysql://user:password@host:3306/dbname
#
# MySQL notes:
#  - mysqlclient>=2.2.1 is required (see requirements.txt).
#  - utf8mb4 is forced below so Persian (Farsi) text, and any emoji, store
#    correctly — MySQL's connection default is often latin1 or the legacy
#    3-byte utf8, neither of which can hold the full Unicode range.
#  - With TIME_ZONE='UTC' (below), Django's MySQL backend does NOT need the
#    mysql_tzinfo_to_sql time zone tables loaded, because no CONVERT_TZ()
#    call is generated when the connection timezone already matches 'UTC'.
#    If you ever change TIME_ZONE away from 'UTC', load those tables first
#    (see Django docs: "Time zone data" for MySQL).

_db_url = config('DATABASE_URL', default='')
# Individual DB env vars — bypass dj-database-url parsing which can mangle
# passwords containing special characters (e.g. $$, @, #).  When any of
# DB_NAME / DB_USER / DB_PASSWORD are set, they take precedence over
# DATABASE_URL so the raw password is passed to MySQL without URL decoding.
_db_name = config('DB_NAME', default='')
_db_user = config('DB_USER', default='')
_db_password = config('DB_PASSWORD', default='')
_db_host = config('DB_HOST', default='localhost')
_db_port = config('DB_PORT', default='3306')

if _db_name and _db_user and _db_password:
    # Direct connection — no URL encoding/decoding step.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': _db_name,
            'USER': _db_user,
            'PASSWORD': _db_password,
            'HOST': _db_host,
            'PORT': _db_port,
            'CONN_MAX_AGE': 0,
            'OPTIONS': {
                'charset': 'utf8mb4',
            },
        }
    }
    _db_ssl_ca = config('DB_SSL_CA', default='')
    if _db_ssl_ca:
        DATABASES['default']['OPTIONS']['ssl'] = {'ca': _db_ssl_ca}
elif _db_url:
    try:
        import dj_database_url
        DATABASES = {'default': dj_database_url.parse(_db_url, conn_max_age=0)}
    except ImportError:
        raise RuntimeError(
            'DATABASE_URL is set but dj-database-url is not installed. '
            'Run: pip install dj-database-url'
        )

    if DATABASES['default'].get('ENGINE') == 'django.db.backends.mysql':
        DATABASES['default'].setdefault('OPTIONS', {})
        DATABASES['default']['OPTIONS'].setdefault('charset', 'utf8mb4')
        _db_ssl_ca = config('DB_SSL_CA', default='')
        if _db_ssl_ca:
            DATABASES['default']['OPTIONS']['ssl'] = {'ca': _db_ssl_ca}
else:
    # Local development default: SQLite file in the project root.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# SECURITY: LocMemCache is per-process -- each Gunicorn worker has its own
# cache instance. Rate-limiting counters (registration, password reset,
# email confirm) are NOT shared across workers, so the effective rate limit
# is multiplied by the number of workers.
#
# In production, use REDIS_URL env var to enable Redis-backed caching:
#   REDIS_URL=redis://localhost:6379/0
# When REDIS_URL is not set, LocMemCache is used for local development only.
#
# WARNING: Running LocMemCache in production with multiple Gunicorn workers
# effectively multiplies all rate limits by the worker count, allowing
# brute-force and abuse campaigns to bypass rate limiting entirely.

_redis_url = config('REDIS_URL', default='')

if _redis_url and not _RUNNING_TESTS:
    try:
        import django_redis  # noqa: F401
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': _redis_url,
            }
        }
    except ImportError:
        import warnings
        warnings.warn(
            'REDIS_URL is set but django-redis is not installed. '
            'Falling back to LocMemCache. '
            'Install with: pip install django-redis',
            RuntimeWarning,
        )
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    if not DEBUG and not _RUNNING_TESTS:
        import warnings
        warnings.warn(
            'REDIS_URL is not set in production (DEBUG=False). '
            'LocMemCache is per-process — rate limits are NOT shared '
            'across Gunicorn workers. Set REDIS_URL for proper rate limiting.',
            RuntimeWarning,
        )

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

# Use the custom user model defined in accounts/models.py instead of
# Django's built-in User.  This must be set before any migration is created.
AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_URL = 'accounts:login'
# After a successful login, redirect to the user panel (not the default
# /accounts/profile/ which does not exist in this project).
LOGIN_REDIRECT_URL = 'accounts:panel'
# After logout, go to the home page.  Without this Django redirects to
# /accounts/logout/ (the django.contrib.auth view) which now has no route.
LOGOUT_REDIRECT_URL = 'home'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Password hashing: prefer Argon2 (memory-hard) over PBKDF2 for better
# resistance to GPU-based offline cracking. Falls back to PBKDF2 if
# argon2-cffi is not installed.
try:
    import argon2  # noqa: F401
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.Argon2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    ]
except ImportError:
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    ]

AUTHENTICATION_BACKENDS = [
    # Axes standalone backend MUST be listed first so lockouts are enforced
    # before the standard ModelBackend validates credentials.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ---------------------------------------------------------------------------
# Brute-force protection (django-axes)
# ---------------------------------------------------------------------------

# Lock out the IP/username combination after 5 consecutive failures.
AXES_FAILURE_LIMIT = 5
# Unlock automatically after 1 hour of no failed attempts.
AXES_COOLOFF_TIME = timedelta(hours=1)
# Reset failed attempts after a successful login
AXES_RESET_ON_SUCCESS = True
# Track by IP and username (dual-key lockout).
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]

# Tell Axes how many trusted reverse proxies sit in front of Django (typically
# one: Nginx → Gunicorn). Without this, REMOTE_ADDR is the Nginx loopback IP
# (127.0.0.1) and IP-based lockout is completely ineffective — every client
# would share the same "IP" key.
AXES_IPWARE_PROXY_COUNT = 1
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR"]

# Disable Axes within the Django admin; the custom panel handles its own auth.
AXES_ENABLE_ADMIN = False

# ---------------------------------------------------------------------------
# Content Security Policy (Django 6.0 built-in)
# ---------------------------------------------------------------------------
# All assets (JS, CSS, fonts) are self-hosted, so no external origins needed.
# frame-src and object-src are explicitly denied to prevent clickjacking and
# plugin-based attacks. Enforced (not report-only) via SECURE_CSP, applied by
# django.middleware.csp.ContentSecurityPolicyMiddleware (see MIDDLEWARE above).
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    # All JS, CSS, and fonts are self-hosted — no external CDN or
    # Google Fonts domains are needed.
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "frame-src": [CSP.NONE],
    "object-src": [CSP.NONE],
}
# CSP deployment note: To deploy in report-only mode first (recommended for
# new deployments), use Content-Security-Policy-Report-Only header via
# custom middleware or Nginx before switching to enforcement. The SECURE_CSP
# setting above enforces the policy. To add violation reporting, add a
# "report-uri" directive to SECURE_CSP.

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
# The site supports English (default) and Persian (Farsi).
# Translation files live in locale/fa/LC_MESSAGES/django.{po,mo}.
LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', 'English'),
    ('fa', 'فارسی'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Two separate log files are written:
#   logs/security.log  – django-axes auth events (locked IPs, failures, …).
#   logs/audit.log     – application-level actions (post CRUD, role changes, …).
# The directory is created automatically if it doesn't exist on startup.

LOG_DIR = BASE_DIR / "logs"
try:
    LOG_DIR.mkdir(exist_ok=True)
except OSError:
    pass

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "security": {
            "format": "[{asctime}] {levelname} {message}",
            "style": "{",
        },
    },

    "handlers": {
        "security_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "security.log",
            "formatter": "security",
        },
        "audit_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/audit.log",
            "formatter": "security",
        },
        "email_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "email_confirmation.log",
            "formatter": "security",
        },
    },

    "loggers": {
        # Captures all django-axes lockout / attempt events.
        "axes": {
            "handlers": ["security_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Application audit trail — written by accounts.utils.audit().
        "audit": {
            "handlers": ["audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Email confirmation token verification (registration + confirmation).
        "accounts.email_verification": {
            "handlers": ["email_file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'
# collectstatic writes to this directory; WhiteNoise serves from it.
STATIC_ROOT = BASE_DIR / 'staticfiles'

# STORAGES (Django >= 4.2) replaces the old STATICFILES_STORAGE /
# DEFAULT_FILE_STORAGE settings, which were removed entirely in Django 5.1 —
# on Django 6 a bare `STATICFILES_STORAGE = '...'` setting is just ignored,
# silently falling back to the plain (non-hashed, non-compressed)
# StaticFilesStorage and breaking WhiteNoise's long-lived cache headers.
# CompressedManifestStaticFilesStorage adds content-addressed filenames
# (e.g. style.abc123.css) for long-lived browser caching.
#
# BUG FIX: CompressedManifestStaticFilesStorage requires staticfiles.json,
# which is only written by `manage.py collectstatic`. `manage.py test` never
# runs collectstatic, so every {% static %} tag in every template raised
# `ValueError: Missing staticfiles manifest entry for '...'` and every view
# test that rendered a template (i.e. almost all of them) failed/errored.
# Auto-detect test runs (manage.py test / pytest) and fall back to the plain
# StaticFilesStorage, which resolves STATIC_URL + path directly with no
# manifest required. Production deployments (which run collectstatic before
# serving traffic) are unaffected and keep the hashed/compressed storage.
import sys  # noqa: E402  (kept local to this check, not used elsewhere)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if _RUNNING_TESTS else
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# In development the console backend prints emails to stdout.
# In production set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# and supply EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD.

EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL', default='noreply@OpenSrcPersian.example'
)

# ---------------------------------------------------------------------------
# Unfold admin theme
# ---------------------------------------------------------------------------
# Replaces the default Django admin with a modern, branded UI.
# Tab groups keep related models together in the admin sidebar.
UNFOLD = {
    'SITE_TITLE': 'OpenSrc Persian Admin',
    'SITE_HEADER': 'OpenSrc Admin',
    'SITE_URL': '/',
    'SITE_ICON': None,
    # Purple accent palette matching the site brand.
    'COLORS': {
        'primary': {
            '50':  '250 245 255',
            '100': '243 232 255',
            '200': '233 213 255',
            '300': '216 180 254',
            '400': '192 132 252',
            '500': '168 85 247',
            '600': '147 51 234',
            '700': '126 34 206',
            '800': '107 33 168',
            '900': '88 28 135',
            '950': '59 7 100',
        },
    },
    # Group posts-related models under one tab bar and users under another.
    'TABS': [
        {
            'models': ['posts.post', 'posts.category', 'posts.subcategory', 'posts.tag'],
            'items': [
                {'title': 'Posts',      'link': '/admin/posts/post/'},
                {'title': 'Categories', 'link': '/admin/posts/category/'},
                {'title': 'Tags',       'link': '/admin/posts/tag/'},
            ],
        },
        {
            'models': ['accounts.customuser', 'accounts.userprofile'],
            'items': [
                {'title': 'Users',    'link': '/admin/accounts/customuser/'},
                {'title': 'Profiles', 'link': '/admin/accounts/userprofile/'},
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Production security hardening (applied only when DEBUG=False)
# ---------------------------------------------------------------------------
# These settings are skipped in development to avoid breaking HTTP localhost
# workflows; they are mandatory for any internet-facing deployment.

if not DEBUG:
    # Tell browsers to only access the site over HTTPS for one year.
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Allow the domain to be included in browser HSTS preload lists.
    SECURE_HSTS_PRELOAD = True
    # Redirect all HTTP requests to HTTPS.
    # Line 609: was hardcoded True
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)

# Lines 611-612: were hardcoded True  
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Prevent the site from being embedded in iframes (clickjacking protection).
    X_FRAME_OPTIONS = 'DENY'
    # Signal to Django that the upstream reverse proxy (Nginx/Gunicorn) terminates SSL.
    # Without this, request.is_secure() returns False behind a proxy, causing
    # SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, and open-redirect checks to fail.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')