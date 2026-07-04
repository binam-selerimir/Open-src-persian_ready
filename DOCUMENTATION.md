# OpenSrcPersian — Full Developer Documentation

> Django 6.0 CMS for open-source software news. Bilingual (EN/FA), production-ready.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Quick Start](#2-quick-start)
3. [Architecture](#3-architecture)
4. [Apps Reference](#4-apps-reference)
5. [Models — Complete Field Reference](#5-models)
6. [Views — Complete Function Reference](#6-views)
7. [URL Patterns](#7-url-patterns)
8. [Forms — Validation Logic](#8-forms)
9. [Security System](#9-security-system)
10. [HTML Sanitization Pipeline](#10-html-sanitization-pipeline)
11. [Media Upload System](#11-media-upload-system)
12. [Template Tags & Filters](#12-template-tags--filters)
13. [Templates — File Map](#13-templates)
14. [Static Assets — CSS/JS](#14-static-assets)
15. [Settings — All Configuration](#15-settings)
16. [Database Schema & Indexes](#16-database-schema--indexes)
17. [Caching Strategy](#17-caching-strategy)
18. [Testing](#18-testing)
19. [Deployment](#19-deployment)
20. [File Reference Index](#20-file-reference-index)

---

## 1. Project Overview

OpenSrcPersian is a GNU-inspired open-source software news platform with Persian (Farsi) RTL support. It uses Django 6.0, MySQL (production), Gunicorn, and Nginx.

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0, Python 3.12+ |
| Database | MySQL (prod), SQLite (dev/test) |
| Server | Gunicorn + Nginx |
| HTML Sanitization | bleach 6.x |
| Markdown Rendering | markdown 3.7+ |
| Image Processing | Pillow 10.x |
| MIME Detection | python-magic |
| Rich Text Editor | Quill.js |
| Dropdowns | Tom Select |
| Admin Theme | django-unfold |
| Brute-force Protection | django-axes |
| Static Files | WhiteNoise |

### Apps

| App | Purpose | Files |
|-----|---------|-------|
| `core` | Homepage, static pages, base templates, CSP middleware, context processors | 8 files |
| `posts` | Articles, categories, subcategories, tags, post types, image processing, view counter, markdown upload | 15 files |
| `accounts` | Custom user model, auth views, admin panel, audit log | 12 files |
| `search` | Full-text search across posts | 3 files |
| `comments` | User comments with admin approval workflow | 6 files |
| `forum` | Community forum — boards, threads, posts with moderation | 15 files |

---

## 2. Quick Start

```bash
# Create .env file
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Seed demo data
python manage.py seed_pages
python manage.py seed_posts

# Run dev server
python manage.py runserver

# Run tests
python manage.py test
```

### Required Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | Django secret key (app crashes without it) |
| `DEBUG` | No | `True` | Debug mode |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DATABASE_URL` | No | SQLite | `mysql://user:pass@host/db` |
| `CSRF_TRUSTED_ORIGINS` | No | `''` | Comma-separated trusted origins |
| `EMAIL_HOST` | No | `''` | SMTP host |
| `EMAIL_PORT` | No | `587` | SMTP port |
| `EMAIL_HOST_USER` | No | `''` | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | `''` | SMTP password |
| `DEFAULT_FROM_EMAIL` | No | `''` | Sender email address |

---

## 3. Architecture

### Request Flow

```
Browser → Nginx → Gunicorn → Django Middleware Stack → URL Router → View → Template → Response
```

### Middleware Stack (order matters)

| # | Middleware | File:Line | Purpose |
|---|-----------|-----------|---------|
| 1 | `SecurityMiddleware` | Django built-in | HTTPS redirect, HSTS |
| 2 | `WhiteNoiseMiddleware` | whitenoise | Static file serving |
| 3 | `SessionMiddleware` | Django built-in | Session management |
| 4 | `LocaleMiddleware` | Django built-in | i18n language detection |
| 5 | `CommonMiddleware` | Django built-in | URL normalization |
| 6 | `CsrfViewMiddleware` | Django built-in | CSRF protection |
| 7 | `AuthenticationMiddleware` | Django built-in | User session |
| 8 | `MessageMiddleware` | Django built-in | Flash messages |
| 9 | `XFrameOptionsMiddleware` | Django built-in | Clickjacking protection |
| 10 | `AxesMiddleware` | django-axes | Brute-force protection |
| 11 | `ContentSecurityPolicyMiddleware` | django-csp | CSP headers |
| 12 | `AdminCSPOverrideMiddleware` | `core/middleware.py:16` | Relaxes CSP for /admin/ |

### Signal System

| Signal | File:Line | Trigger | Action |
|--------|-----------|---------|--------|
| `post_save(User)` | `accounts/signals.py:30` | User created/updated | Ensures UserProfile row exists via `get_or_create` |

### Context Processor

| Processor | File:Line | Injects | Cache |
|-----------|-----------|---------|-------|
| `global_context` | `core/context_processors.py:50` | `categories`, `latest_posts` (5), `nav_pages` | 5 min LocMemCache |

---

## 4. Apps Reference

### accounts App

| File | Lines | Purpose |
|------|-------|---------|
| `accounts/views/auth.py` | 139 | Login, logout, register, email confirmation |
| `accounts/views/admin/__init__.py` | — | Re-exports all admin views for URL compatibility |
| `accounts/views/admin/` (package) | — | Admin panel views (split from monolith) |
| `accounts/views/admin/_common.py` | — | Shared `_admin_login_required`, `_safe_int` helpers |
| `accounts/views/admin/_posts.py` | — | Post CRUD, media upload, bulk actions |
| `accounts/views/admin/_taxonomy.py` | — | Category/subcategory/post type CRUD |
| `accounts/views/admin/_comments.py` | — | Comment management |
| `accounts/views/admin/_users.py` | — | User management (superuser only) |
| `accounts/views/admin/_certificates.py` | — | Certificate CRUD + grants |
| `accounts/views/panel.py` | 41 | User panel: dashboard, edit profile, public profile |
| `accounts/views/__init__.py` | 16 | View exports |
| `accounts/models.py` | 148 | CustomUser, UserProfile, AuditLog |
| `accounts/forms.py` | 186 | LoginForm, RegisterForm, UserEditForm, ProfileEditForm |
| `accounts/utils.py` | 89 | get_client_ip, audit, check_rate_limit |
| `accounts/email_verification.py` | 94 | Token-based email confirmation |
| `accounts/signals.py` | 25 | User profile auto-creation |
| `accounts/admin.py` | 54 | Django admin registrations |
| `accounts/otp.py` | 58 | TOTP/OTP utilities (inactive) |
| `accounts/urls.py` | 63 | 17 URL patterns |

### posts App

| File | Lines | Purpose |
|------|-------|---------|
| `posts/models.py` | 328 | Post, Category, Subcategory, PostType, Tag (+ body_md_file field) |
| `posts/views.py` | 220 | Post list, detail, category, subcategory, AJAX endpoint |
| `posts/forms.py` | 236 | PostForm with body_mode toggle, markdown file validation |
| `posts/utils/sanitization.py` | 196 | HTML sanitization pipeline + render_markdown_body() |
| `posts/utils/media.py` | 71 | Media upload validation |
| `posts/utils/__init__.py` | 19 | Utils exports |
| `posts/image_processing.py` | 146 | Cover/avatar processing with Pillow |
| `posts/feeds.py` | 54 | RSS 2.0 feed |
| `posts/sitemaps.py` | 29 | XML sitemap |
| `posts/templatetags/post_extras.py` | 229 | 7 template filters (incl. render_body_for_post) |
| `posts/admin.py` | 51 | Django admin registrations |
| `posts/urls.py` | 34 | 6 URL patterns |

### core App

| File | Lines | Purpose |
|------|-------|---------|
| `core/views.py` | 54 | Home, about, page detail, 404/500 handlers |
| `core/models.py` | 43 | Page model |
| `core/context_processors.py` | 71 | Global nav context with caching |
| `core/middleware.py` | 83 | CSP override for admin |
| `core/admin.py` | 18 | Django admin registration |
| `core/urls.py` | 22 | 3 URL patterns |

### search App

| File | Lines | Purpose |
|------|-------|---------|
| `search/views.py` | 140 | Full-text search with filters |
| `search/urls.py` | 25 | 2 URL patterns |

### comments App

| File | Lines | Purpose |
|------|-------|---------|
| `comments/models.py` | 34 | Comment model with admin approval |
| `comments/forms.py` | 33 | CommentForm (body only — name/email from account) |
| `comments/views.py` | 49 | add_comment — rate-limited, login-required |
| `comments/admin.py` | 12 | Django admin registration |
| `comments/urls.py` | 8 | Comment URL pattern |
| `comments/tests.py` | 395 | 32 tests (model, form, views, admin, visibility) |

### forum App

| File | Lines | Purpose |
|------|-------|---------|
| `forum/models.py` | — | Board, Thread, ForumPost models with soft-delete |
| `forum/views.py` | — | Index, board, thread, new, reply, edit, delete, toggle, upload media |
| `forum/forms.py` | — | NewBoardForm, NewThreadForm, ReplyForm with shared `_sanitize_forum_body()` helper |
| `forum/urls.py` | 12 | URL patterns (Unicode/Persian slug support) |
| `forum/admin.py` | — | BoardAdmin, ThreadAdmin, ForumPostAdmin (django-unfold) |
| `forum/templatetags/forum_extras.py` | — | forum_post_count filter |
| `forum/static/forum/forum-editor.js` | — | Quill.js editor for forum reply/new-thread/edit-post forms |
| `forum/tests.py` | — | 73 tests (models, views, forms, template tags, upload) |

---

## 5. Models

### CustomUser (`accounts/models.py:41`)

Extends `AbstractUser`. AUTH_USER_MODEL = 'accounts.CustomUser'.

| Field | Type | Line | Constraints | Notes |
|-------|------|------|-------------|-------|
| `email` | EmailField | 54 | unique=True | Login identifier |
| `bio_en` | TextField | 55 | blank=True | English biography |
| `bio_fa` | TextField | 56 | blank=True | Persian biography |
| `avatar` | ImageField | 59 | upload_to='avatars/', blank, null | Processed by process_avatar_image |
| `website` | URLField | 60 | blank=True, validators=[_validate_safe_url] | Blocks javascript:/data:/vbscript: and // |
| `is_site_admin` | BooleanField | 61 | default=False | Grants access to panel admin tabs |

**Methods:**
- `get_full_name_display()` — `accounts/models.py:66` — Returns 'First Last' or username

### UserProfile (`accounts/models.py:71`)

OneToOneField to CustomUser. Auto-created by signal.

| Field | Type | Line | Constraints |
|-------|------|------|-------------|
| `user` | OneToOneField | 82 | CASCADE, related_name='profile' |
| `display_name` | CharField(150) | 88 | blank=True |
| `headline_en` | CharField(255) | 90 | blank=True |
| `headline_fa` | CharField(255) | 93 | blank=True |
| `skills` | TextField | 95 | blank=True, comma-separated |
| `linkedin_url` | URLField | 96 | blank=True, validators=[_validate_safe_url] |
| `github_url` | URLField | 97 | blank=True, validators=[_validate_safe_url] |
| `telegram` | CharField(80) | 99 | blank=True, RegexValidator(r'^[a-zA-Z0-9_]{5,32}$') |

**Methods:**
- `get_skills_list()` — `accounts/models.py:116` — Splits comma-separated skills into list

### AuditLog (`accounts/models.py:123`)

Append-only log. Read-only in Django admin (no add/change/delete).

| Field | Type | Line | Notes |
|-------|------|------|-------|
| `user` | ForeignKey(User, SET_NULL) | 154 | null=True, blank=True |
| `action` | CharField(50) | 161 | choices=ACTIONS (10 types) |
| `description` | TextField | 164 | blank=True |
| `ip_address` | GenericIPAddressField | 167 | null=True, blank=True |
| `created_at` | DateTimeField | 170 | auto_now_add=True |

**Action Types:** LOGIN, LOGIN_FAILED, LOGOUT, PASSWORD_RESET, EMAIL_VERIFIED, POST_CREATE, POST_DELETE, POST_EDIT, ROLE_CHANGE, ADMIN_LOGIN

### Certificate (`accounts/models.py`)

Badge template created and managed by superusers.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `name` | CharField(150) | unique=True | |
| `name_fa` | CharField(150) | blank=True | Persian name |
| `description` | TextField | blank=True | |
| `description_fa` | TextField | blank=True | |
| `icon` | ImageField | upload_to='certificates/icons/', blank, null | Processed to 256x256 |
| `accent_color` | CharField(7) | default='#4f46e5', validators=[_hex_color_validator] | |
| `is_active` | BooleanField | default=True | Inactive certs cannot be granted |
| `created_by` | ForeignKey(User, SET_NULL) | null=True, blank=True | |
| `created_at` | DateTimeField | auto_now_add=True | |
| `updated_at` | DateTimeField | auto_now=True | |

### UserCertificate (`accounts/models.py`)

Granted certificate linking a user to a Certificate.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `user` | ForeignKey(User, CASCADE) | related_name='certificates' | |
| `certificate` | ForeignKey(Certificate, CASCADE) | related_name='grants' | |
| `granted_by` | ForeignKey(User, SET_NULL) | null=True, blank=True | |
| `granted_at` | DateTimeField | auto_now_add=True | |
| `note` | TextField | blank=True | Shown to user |
| `is_visible` | BooleanField | default=True | User can hide from profile |

**Constraints:** UniqueConstraint on (user, certificate) — `accounts/models.py`
**Indexes:** Index on (user, is_visible) — `usercert_user_visible_idx`

### Category (`posts/models.py:47`)

| Field | Type | Line | Constraints |
|-------|------|------|-------------|
| `name_en` | CharField(120) | 56 | — |
| `name_fa` | CharField(120) | 57 | — |
| `slug` | SlugField(120) | 58 | unique=True, allow_unicode=True |
| `description_en` | TextField | 59 | blank=True |
| `description_fa` | TextField | 60 | blank=True |
| `order` | PositiveSmallIntegerField | 62 | default=0 |

### Subcategory (`posts/models.py:78`)

| Field | Type | Line | Constraints |
|-------|------|------|-------------|
| `category` | ForeignKey(Category, CASCADE) | 86 | related_name='subcategories' |
| `name_en` | CharField(120) | 89 | — |
| `name_fa` | CharField(120) | 90 | — |
| `slug` | SlugField(120) | 91 | allow_unicode=True |

**Constraints:** UniqueConstraint on (category, slug) — `posts/models.py:95-96`

### PostType (`posts/models.py:113`)

| Field | Type | Line | Constraints |
|-------|------|------|-------------|
| `name_en` | CharField(80) | 122 | — |
| `name_fa` | CharField(80) | 123 | blank=True |
| `slug` | SlugField(40) | 124 | unique=True, allow_unicode=True |
| `accent_color` | CharField(7) | 125 | default='#ffcc00', validators=[_hex_color_validator] |
| `order` | PositiveSmallIntegerField | 131 | default=0 |

**Methods:**
- `label(language_code)` — `posts/models.py:141` — Returns localised name

### Tag (`posts/models.py:148`)

| Field | Type | Line | Constraints |
|-------|------|------|-------------|
| `name` | CharField(80) | 156 | unique=True |
| `slug` | SlugField(80) | 157 | unique=True, allow_unicode=True |

### Post (`posts/models.py:167`)

| Field | Type | Line | Constraints | Notes |
|-------|------|------|-------------|-------|
| `title` | CharField(255) | 194 | — | |
| `slug` | SlugField(255) | 195 | unique=True, allow_unicode=True | URL identifier |
| `category` | ForeignKey(Category, PROTECT) | 196 | related_name='posts' | Cannot delete category with posts |
| `subcategory` | ForeignKey(Subcategory, SET_NULL) | 199 | null=True, blank=True | Deleting subcategory preserves posts |
| `post_type` | ForeignKey(PostType, PROTECT) | 203 | related_name='posts' | Cannot delete type with posts |
| `tags` | ManyToManyField(Tag) | 206 | blank=True, related_name='posts' | |
| `author_name` | CharField(200) | 208 | blank=True | Display name (distinct from publisher FK) |
| `publisher` | ForeignKey(User, SET_NULL) | 212 | null=True, blank=True | Deleting user preserves posts |
| `summary` | TextField | 217 | blank=True | Short excerpt |
| `body` | TextField | 218 | — | HTML from WYSIWYG, sanitized on save |
| `body_md_file` | FileField | 219 | upload_to='posts/md/', blank=True, null=True | Markdown file (alternative to body) |
| `cover_image` | ImageField | 225 | upload_to='posts/covers/', blank, null | Resized to 1200x675 JPEG |
| `cover_alt` | CharField(255) | 220 | blank=True | Accessibility text |
| `attachment` | FileField | 224 | upload_to='posts/files/', blank, null | Validated in PostForm |
| `pub_date` | DateTimeField | 227 | default=timezone.now | |
| `created_at` | DateTimeField | 228 | auto_now_add=True | |
| `updated_at` | DateTimeField | 229 | auto_now=True | |
| `is_visible` | BooleanField | 230 | default=True | Visibility toggle |
| `view_count` | PositiveIntegerField | 231 | default=0, editable=False | Total page views (all users see) |
| `unique_view_count` | PositiveIntegerField | 232 | default=0, editable=False | Unique IP views (superuser only) |

**Manager:** `PublishedPostManager` — `posts/models.py:42` — `.published()` returns `filter(is_visible=True)`

**Methods:**
- `save()` — `posts/models.py:254` — Sanitizes body via clean_post_body; re-raises ValidationError; escapes on unexpected error
- `get_absolute_url()` — `posts/models.py:250` — Returns `/posts/<slug>/`
- `attachment_filename` — `posts/models.py:289` — Property: bare filename
- `reading_time` — `posts/models.py:295` — cached_property: estimated minutes at 200 wpm

### Page (`core/models.py:21`)

| Field | Type | Line | Constraints |
|-------|------|------|-------------|
| `title` | CharField(255) | 32 | — |
| `slug` | SlugField(255) | 33 | unique=True |
| `body` | TextField | 34 | — |
| `created_at` | DateTimeField | 35 | auto_now_add=True |
| `updated_at` | DateTimeField | 36 | auto_now=True |
| `show_in_nav` | BooleanField | 38 | default=False |
| `nav_order` | PositiveSmallIntegerField | 40 | default=0 |

### Comment (`comments/models.py:5`)

| Field | Type | Line | Constraints | Notes |
|-------|------|------|-------------|-------|
| `post` | ForeignKey(Post, CASCADE) | 14 | related_name='comments' | |
| `author_name` | CharField(150) | 17 | — | Set from user's account |
| `author_email` | EmailField | 18 | — | Set from user's account |
| `body` | TextField | 19 | — | Sanitized with bleach |
| `is_approved` | BooleanField | 20 | default=False | Requires admin approval |
| `ip_address` | GenericIPAddressField | 21 | null=True, blank=True | |
| `created_at` | DateTimeField | 22 | auto_now_add=True | |

**Indexes:**
- `comment_post_approved_idx` — (post, is_approved) — `comments/models.py:29`
- `comment_created_idx` — (-created_at) — `comments/models.py:30`

---

## 6. Views

### Auth Views (`accounts/views/auth.py`)

| View | Line | Method | Auth | Rate Limit | Description |
|------|------|--------|------|------------|-------------|
| `login_view` | 17 | GET/POST | No | — | Timing-safe login with _DUMMY_HASH, audit logging, inactive account detection |
| `logout_view` | 68 | GET/POST | No | — | Audit logging before logout, redirects to home |
| `register_view` | 76 | GET/POST | No | 5/5min | Atomic create, email confirmation, rollback on SMTP failure |
| `confirm_email_sent` | 114 | GET | No | — | Static info page |
| `resend_confirmation_email` | 118 | POST | No | 3/hour | Re-sends confirmation email, prevents enumeration |
| `confirm_email_view` | 146 | GET | No | 10/hour | Validates token, activates account |

**Login Security Flow (`accounts/views/auth.py:17-56`):**
1. Check if already authenticated → redirect to panel
2. Validate `?next=` with `url_has_allowed_host_and_scheme` → prevent open redirect
3. Run `_check_password(password, _DUMMY_HASH)` → equalize timing
4. Call `authenticate()` → get user or None
5. If authenticated: login, audit, redirect
6. If failed: query candidate, run `_check_password` again, check if inactive
7. If inactive with correct password: show "confirm email" message
8. Otherwise: generic "invalid credentials" message

### User Panel Views (`accounts/views/panel.py`)

| View | Line | Method | Auth | Description |
|------|------|--------|------|-------------|
| `panel_dashboard` | 16 | GET | Yes | Profile overview page |
| `edit_profile` | 21 | GET/POST | Yes | Edit user + profile in transaction.atomic() |
| `public_profile` | 39 | GET | No | Public profile with published posts and visible certificates |
| `user_certificates` | — | GET | Yes | User's own certificates page |

### Admin Panel Views (`accounts/views/admin/`)

| View | File | Method | Auth | Description |
|------|------|--------|------|-------------|
| `upload_post_media` | `_posts.py` | POST | Admin | AJAX upload: returns JSON {url, type, name} |
| `admin_new_post` | `_posts.py` | GET/POST | Admin | Create new post with audit |
| `admin_posts` | `_posts.py` | GET/POST | Admin | Paginated list with search, filters, sort, bulk actions, comment counts (staff: own posts only, superuser: all) |
| `admin_edit_post` | `_posts.py` | GET/POST | Admin | Edit existing post + per-post comment management |
| `admin_delete_post` | `_posts.py` | GET/POST | Admin | Delete with confirmation |
| `admin_post_taxonomy` | `_taxonomy.py` | GET/POST | Admin | Category/subcategory/post type CRUD |
| `admin_tags` | `_taxonomy.py` | GET/POST | Admin | Tag create/delete |
| `admin_comments` | `_comments.py` | GET/POST | Admin | All comments management with bulk actions |
| `admin_users` | `_users.py` | GET/POST | Superuser | Toggle is_active, is_site_admin with last-admin protection |
| `admin_certificates` | `_certificates.py` | GET/POST | Superuser | Certificate CRUD: create, edit, toggle active, delete |
| `admin_grant_certificate` | `_certificates.py` | GET/POST | Superuser | Grant/revoke certificates to users with search |

**Bulk Actions (`accounts/views/admin.py:112-131`):**
- `publish` → `Post.objects.filter(pk__in=pks).update(is_visible=True)`
- `hide` → `Post.objects.filter(pk__in=pks).update(is_visible=False)`
- `delete` → `Post.objects.filter(pk__in=pks).delete()`
- Invalid PKs → warning message

**Taxonomy CRUD (`accounts/views/admin.py:178-293`):**
- `_taxonomy_create` → `get_or_create(slug=slug, defaults=defaults)`
- `_taxonomy_edit` → Validates accent_color hex, category FK existence, slug uniqueness
- `_taxonomy_delete` → Refuses if related items exist
- `_handle_taxonomy_post` → Routes POST actions to create/edit/delete handlers

### Post Views (`posts/views.py`)

| View | Line | Method | Auth | Description |
|------|------|--------|------|-------------|
| `post_list` | 33 | GET | No | Paginated post browser with ?category, ?subcategory, ?type, ?tag filters |
| `category_detail` | 93 | GET | No | Category landing page |
| `subcategory_detail` | 109 | GET | No | Subcategory landing page (validates parent) |
| `post_detail` | 126 | GET | No | Full article with 5 related posts, dual view counts (view_count for all, unique_view_count for superuser) |
| `subcategories_json` | 158 | GET | Yes | AJAX: JSON subcategories for ?category= or ?category_slug= |

### Search View (`search/views.py:58`)

| View | Line | Method | Auth | Rate Limit | Description |
|------|------|--------|------|------------|-------------|
| `search_page` | 58 | GET | No | 30/min | Full-text search with q, type, category, subcategory, tag, date_from, date_to filters |

### Core Views (`core/views.py`)

| View | Line | Method | Auth | Description |
|------|------|--------|------|-------------|
| `home` | 22 | GET | No | Homepage with 5 latest visible posts |
| `page_detail` | 34 | GET | No | Flat Page by slug |
| `about` | 45 | GET | No | Static About page |
| `page_not_found` | 54 | GET | No | Custom 404 handler |
| `server_error` | 65 | GET | No | Custom 500 handler with DB outage fallback |

### Comment Views (`comments/views.py`)

| View | Line | Method | Auth | Rate Limit | Description |
|------|------|--------|------|------------|-------------|
| `add_comment` | 15 | POST | Yes | 5/5min | Create comment (uses account name/email) |

### Forum Views (`forum/views.py`)

| View | Line | Method | Auth | Rate Limit | Description |
|------|------|--------|------|------------|-------------|
| `forum_index` | 17 | GET | No | — | Board listing with stats and last post |
| `new_board` | 33 | GET/POST | Admin | — | Create new board (site admin only) |
| `board_detail` | 48 | GET | No | — | Thread listing for a board, paginated (`THREADS_PER_PAGE`/page) |
| `thread_detail` | 65 | GET | No | — | Thread with paginated posts (`POSTS_PER_PAGE`/page), reply form, mod actions |
| `new_thread` | 96 | GET/POST | Yes | `FORUM_NEW_THREAD_RATE_LIMIT` | Create new thread |
| `reply` | 131 | POST | Yes | `FORUM_REPLY_RATE_LIMIT` | Post reply to thread |
| `edit_post` | 161 | GET/POST | Yes | — | Edit forum post (owner or admin only) |
| `delete_post` | 183 | POST | Yes | — | Soft-delete post (owner or admin, not first post) |
| `delete_thread` | 199 | POST | Admin | — | Soft-delete thread (admin only) |
| `toggle_sticky` | 214 | POST | Admin | — | Pin/unpin thread (admin only) |
| `toggle_close` | 228 | POST | Admin | — | Open/close thread (admin only) |
| `upload_forum_media` | 242 | POST | Yes | `FORUM_UPLOAD_RATE_LIMIT` | AJAX upload for forum editor images |

---

## 7. URL Patterns

### Root URLs (`myproject/urls.py`)

| Pattern | Target | Name |
|---------|--------|------|
| `admin/` | `admin.site.urls` | — |
| `i18n/` | `django.conf.urls.i18n` | Language switcher |
| `sitemap.xml` | sitemap view | — |
| `robots.txt` | TemplateView | — |

### i18n-Prefixed URLs (`myproject/urls.py:99-125`)

All public URLs are prefixed with `/<lang>/` (en or fa).

| Pattern | Target | Name |
|---------|--------|------|
| `''` | `core.urls` | Homepage |
| `posts/` | `posts.urls` (namespace: posts) | Post views |
| `accounts/password_reset/` | `_RateLimitedPasswordResetView` | `password_reset` |
| `accounts/password_reset/done/` | `PasswordResetDoneView` | `password_reset_done` |
| `accounts/reset/<uidb64>/<token>/` | `PasswordResetConfirmView` | `password_reset_confirm` |
| `accounts/reset/done/` | `PasswordResetCompleteView` | `password_reset_complete` |
| `accounts/` | `accounts.urls` (namespace: accounts) | Auth + panel |
| `search/` | `search.urls` (namespace: search) | Search |

### Core URLs (`core/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `''` | `views.home` | `home` |
| `about/` | `views.about` | `about` |
| `page/<slug:slug>/` | `views.page_detail` | `page_detail` |

### Post URLs (`posts/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `''` | `views.post_list` | `post_list` |
| `feed/` | `LatestPostsFeed()` | `post_feed` |
| `subcategories/` | `views.subcategories_json` | `subcategories_json` |
| `category/<slug:cat_slug>/` | `views.category_detail` | `category_detail` |
| `category/<slug:cat_slug>/<slug:sub_slug>/` | `views.subcategory_detail` | `subcategory_detail` |
| `<slug:slug>/` | `views.post_detail` | `post_detail` |

### Account URLs (`accounts/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `login/` | `views.login_view` | `login` |
| `logout/` | `views.logout_view` | `logout` |
| `register/` | `views.register_view` | `register` |
| `confirm-email/sent/` | `views.confirm_email_sent` | `confirm_email_sent` |
| `confirm-email/resend/` | `views.resend_confirmation_email` | `resend_confirmation` |
| `confirm-email/<str:token>/` | `views.confirm_email_view` | `confirm_email` |
| `panel/` | `views.panel_dashboard` | `panel` |
| `panel/edit-profile/` | `views.edit_profile` | `edit_profile` |
| `panel/upload-media/` | `views.upload_post_media` | `upload_post_media` |
| `panel/new-post/` | `views.admin_new_post` | `admin_new_post` |
| `panel/posts/` | `views.admin_posts` | `admin_posts` |
| `panel/posts/<int:pk>/edit/` | `views.admin_edit_post` | `admin_edit_post` |
| `panel/posts/<int:pk>/delete/` | `views.admin_delete_post` | `admin_delete_post` |
| `panel/taxonomy/` | `views.admin_post_taxonomy` | `admin_post_taxonomy` |
| `panel/tags/` | `views.admin_tags` | `admin_tags` |
| `panel/comments/` | `views.admin_comments` | `admin_comments` |
| `panel/users/` | `views.admin_users` | `admin_users` |
| `panel/certificates/` | `views.admin_certificates` | `admin_certificates` |
| `panel/certificates/grant/` | `views.admin_grant_certificate` | `admin_grant_certificate` |
| `panel/my-certificates/` | `views.user_certificates` | `user_certificates` |
| `profile/<str:username>/` | `views.public_profile` | `public_profile` |

### Comment URLs (`comments/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `<slug:slug>/comment/` | `views.add_comment` | `add_comment` |

### Search URLs (`search/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `''` | `views.search_page` | `search` |
| `results/` | `RedirectView → search:search` | Legacy redirect |

### Forum URLs (`forum/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `''` | `views.forum_index` | `index` |
| `new/` | `views.new_board` | `new_board` |
| `upload-media/` | `views.upload_forum_media` | `upload_media` |
| `<board_slug>/` | `views.board_detail` | `board_detail` |
| `<board_slug>/new/` | `views.new_thread` | `new_thread` |
| `<board_slug>/<slug>/` | `views.thread_detail` | `thread_detail` |
| `post/<int:pk>/edit/` | `views.edit_post` | `edit_post` |
| `post/<int:pk>/delete/` | `views.delete_post` | `delete_post` |
| `thread/<int:pk>/reply/` | `views.reply` | `reply` |
| `thread/<int:pk>/delete/` | `views.delete_thread` | `delete_thread` |
| `thread/<int:pk>/sticky/` | `views.toggle_sticky` | `toggle_sticky` |
| `thread/<int:pk>/close/` | `views.toggle_close` | `toggle_close` |

---

## 8. Forms

### LoginForm (`accounts/forms.py:23`)

Simple username + password form (not ModelForm).

| Field | Widget | Autocomplete |
|-------|--------|-------------|
| `username` | TextInput | `username` |
| `password` | PasswordInput | `current-password` |

### RegisterForm (`accounts/forms.py:40`)

| Field | Type | Validation |
|-------|------|------------|
| `username` | CharField | Case-insensitive uniqueness check (`accounts/forms.py:80`) |
| `email` | EmailField | Required + case-insensitive uniqueness (`accounts/forms.py:87`) |
| `first_name` | CharField | — |
| `last_name` | CharField | — |
| `password` | CharField | Runs AUTH_PASSWORD_VALIDATORS (`accounts/forms.py:96`) |
| `password2` | CharField | Must match password (`accounts/forms.py:103`) |

**save()** — `accounts/forms.py:111` — Hashes password, sets is_active=False

### UserEditForm (`accounts/forms.py:126`)

| Field | Widget | Autocomplete |
|-------|--------|-------------|
| `first_name` | TextInput | `given-name` |
| `last_name` | TextInput | `family-name` |
| `bio_en` | Textarea | — |
| `bio_fa` | Textarea | — |
| `avatar` | FileInput | — |
| `website` | URLInput | `url` |

**clean_avatar()** — `accounts/forms.py:158` — Validates:
1. File size ≤ 2 MB (`accounts/forms.py:166`)
2. MIME type via python-magic (`accounts/forms.py:172`)
3. process_avatar_image pipeline (`accounts/forms.py:187`)

### ProfileEditForm (`accounts/forms.py:194`)

| Field | Type |
|-------|------|
| `display_name` | CharField |
| `headline_en` | CharField |
| `headline_fa` | CharField |
| `skills` | TextField |
| `linkedin_url` | URLField |
| `github_url` | URLField |
| `telegram` | CharField (validated by model RegexValidator) |

### PostForm (`posts/forms.py:46`)

| Field | Type | Custom Validation | Label |
|-------|------|-------------------|-------|
| `title` | CharField | — | Title / عنوان |
| `slug` | SlugField | — | Slug / نامک |
| `category` | ModelChoiceField | Required=True (`posts/forms.py:76`) | Category / دسته‌بندی |
| `subcategory` | ModelChoiceField | Populated dynamically (`posts/forms.py:80-103`) | Subcategory / زیردسته |
| `post_type` | ModelChoiceField | Default: 'original_en' or first type (`posts/forms.py:83-89`) | Post Type / نوع نوشته |
| `tags` | ModelManyToManyField | Tom Select searchable (`posts/forms.py:67-72`) | Tags / برچسب‌ها |
| `author_name` | CharField | — | Author Name / نام نویسنده |
| `summary` | Textarea | rows=4 | Summary / خلاصه |
| `body` | Textarea | rows=20, Quill editor | Body / متن |
| `body_mode` | HiddenInput | Non-model field: 'write' or 'upload_md' | Mode selector |
| `body_md_file` | FileInput | Accept: .md, max 1MB | Markdown File / فایل مارک‌داون |
| `cover_image` | FileInput | Accept: image/* (`posts/forms.py:62-66`) | Cover Image / تصویر کاور |
| `cover_alt` | CharField | — | Cover Alt Text / متن جایگزین کاور |
| `attachment` | FileInput | — | Attachment / پیوست |
| `pub_date` | DateTimeInput | type=datetime-local | Publish Date / تاریخ انتشار |
| `is_visible` | BooleanField | — | Show? / نمایش؟ |

Labels are defined in `PostForm.Meta.labels` dict with `_()` translation wrappers. Labels display in the user's active language.

**clean_attachment()** — `posts/forms.py:105` — Validates:
1. Extension in ALLOWED_ATTACHMENT_EXTENSIONS (`posts/forms.py:8`)
2. Size ≤ 100 MB (`posts/forms.py:17`)
3. MIME in ATTACHMENT_ALLOWED_MIMES (`posts/forms.py:19`)

**clean_cover_image()** — `posts/forms.py:135` — Runs process_cover_image()

**clean_body()** — `posts/forms.py:181` — If HTML: clean_post_body(). If plain text: length check.

**clean_body_md_file()** — `posts/forms.py:193` — Validates:
1. File extension must be `.md`
2. File size ≤ 1 MB

**clean()** — `posts/forms.py:208` — Mode-based validation:
- If `body_mode='upload_md'` or file present: requires `body_md_file` (or existing file on edit)
- If `body_mode='write'`: requires `body` text
- `body.required` is set to `False` in `__init__` to allow empty body in upload mode

### Forum Form Sanitization (`forum/forms.py`)

**`_sanitize_forum_body(raw_body)`** — `forum/forms.py:13` — Shared helper called by both `NewThreadForm.clean_body()` and `ReplyForm.clean_body()`.

Steps:
1. Strip whitespace
2. Reject if < 10 characters
3. `bleach.clean()` with `FORUM_SANITIZE_TAGS` and `FORUM_SANITIZE_ATTRIBUTES`
4. Protocols restricted to `http`, `https`, `mailto`

### CommentForm (`comments/forms.py:9`)

Body-only form. author_name and author_email are set from the logged-in user's account in the view — users cannot change them.

| Field | Type | Validation |
|-------|------|------------|
| `body` | CharField(max_length=2000) | bleach sanitized, only p/br/strong/em/a tags allowed |

**clean_body()** — `comments/forms.py:28` — Strips whitespace, rejects empty body, bleach sanitizes

### CertificateForm (`accounts/forms.py`)

ModelForm for creating and editing a Certificate.

| Field | Widget | Validation |
|-------|--------|------------|
| `name` | TextInput | autocomplete=off |
| `name_fa` | TextInput | dir=rtl |
| `description` | Textarea | rows=3 |
| `description_fa` | Textarea | rows=3, dir=rtl |
| `icon` | FileInput | Max 2MB, MIME check via python-magic |
| `accent_color` | TextInput type=color | Hex validated by model validator |
| `is_active` | Checkbox | |

### GrantCertificateForm (`accounts/forms.py`)

Form for granting a certificate to a user. Labels, placeholders, and validation messages are wrapped in `_()` for translation.

| Field | Widget | Validation | Label |
|-------|--------|------------|-------|
| `user` | Select (tom-select) | Active users only | User / کاربر |
| `certificate` | Select (tom-select) | Active certificates only | Certificate / گواهی |
| `note` | Textarea | Optional | Note / یادداشت |

**clean()** — Validates no duplicate (user, certificate) grants and rejects inactive certificates.

---

## 9. Security System

### Authentication & Authorization

| Feature | Implementation | Location |
|---------|---------------|----------|
| Custom user model | `CustomUser` extends `AbstractUser` | `accounts/models.py:41` |
| Email as unique identifier | `email = EmailField(unique=True)` | `accounts/models.py:54` |
| Email confirmation | Token-based with TimestampSigner | `accounts/email_verification.py:63-69` |
| Account activation | `is_active=False` until email confirmed | `accounts/forms.py:120` |
| Brute-force protection | django-axes: 5 failures → 1 hour lockout | `settings.py:260-276` |
| Timing-safe login | `_DUMMY_HASH` bcrypt round before authenticate | `accounts/views/auth.py:30,46` |
| Open redirect prevention | `url_has_allowed_host_and_scheme()` on ?next= | `accounts/views/auth.py:21-25` |
| Last admin protection | Cannot revoke is_site_admin from last admin | `accounts/views/admin/_users.py` |
| Superuser protection | Cannot modify superuser from admin panel | `accounts/views/admin/_users.py` |
| Staff sees own posts | Non-superuser staff users only see their own posts in manage posts | `accounts/views/admin/_posts.py` |
| Superuser sees all posts | Superuser sees all posts in manage posts | `accounts/views/admin/_posts.py` |
| Users tab superuser only | Only superusers can access user management page and see Users tab | `accounts/views/admin/_users.py` |
| Staff comments scoped | Non-superuser staff only moderate comments on their own posts | `accounts/views/admin/_comments.py` |
| Grant inactive cert blocked | GrantCertificateForm rejects inactive certificates | `accounts/forms.py:269-271` |

### Rate Limiting

| Endpoint | Limit | TTL | Location |
|----------|-------|-----|----------|
| Registration | 5/5min per IP | 300s | `accounts/views/auth.py:82` |
| Resend confirmation | 3/hour per IP | 3600s | `accounts/views/auth.py:122` |
| Email confirmation | 10/hour per IP | 3600s | `accounts/views/auth.py:147` |
| Password reset | 5/hour per IP | 3600s | `myproject/urls.py:68` |
| Search | 30/min per IP | 60s | `search/views.py:69` |
| Comments | 5/5min per IP | 300s | `comments/views.py:28` |
| Forum new thread | `FORUM_NEW_THREAD_RATE_LIMIT` (3/10min) per IP | 600s | `forum/views.py:100` |
| Forum reply | `FORUM_REPLY_RATE_LIMIT` (5/5min) per IP | 300s | `forum/views.py:139` |
| Forum upload | `FORUM_UPLOAD_RATE_LIMIT` (10/5min) per IP | 300s | `forum/views.py:245` |

**Implementation:** `accounts/utils.py:93` — `check_rate_limit()` uses Django cache (LocMemCache)

### URL Validation

**`_validate_safe_url()`** — `accounts/models.py:30` — Applied to:
- `CustomUser.website` — `accounts/models.py:60`
- `UserProfile.linkedin_url` — `accounts/models.py:96`
- `UserProfile.github_url` — `accounts/models.py:97`

Rejects: `javascript:`, `data:`, `vbscript:`, `//` (protocol-relative)

### Forum Constants (`forum/views.py`)

Module-level constants for easy tuning:

```python
THREADS_PER_PAGE = 30
POSTS_PER_PAGE = 20

# (count, ttl_seconds) — checked by check_rate_limit().
FORUM_NEW_THREAD_RATE_LIMIT = (3, 600)     # 3 threads per 10 min
FORUM_REPLY_RATE_LIMIT = (5, 300)          # 5 replies per 5 min
FORUM_UPLOAD_RATE_LIMIT = (10, 300)        # 10 uploads per 5 min
```

### Media URL Validation

**`_media_src_allowed()`** — `posts/utils/sanitization.py:70` — Documented security checks:
1. Blocks absolute URLs, data: URIs, protocol-relative and javascript: URLs
2. Decodes up to 3 levels of URL-encoding to catch double/triple-encoded path traversal
3. Strips query strings and fragments before normalisation
4. Rejects any path containing `/../` or starting with `..`
5. Validates file extension against `ALLOWED_INLINE_EXTENSIONS`
6. Must start with `/media/posts/` (must match posts/inline upload_to)

### CSP Headers

| Directive | Value | Source |
|-----------|-------|--------|
| `default-src` | `'self'` | `settings.py:286` |
| `img-src` | `'self' data:` | `settings.py:287` |
| `script-src` | `'self'` | `settings.py:288` |
| `style-src` | `'self'` | `settings.py:289` |
| `font-src` | `'self'` | `settings.py:290` |
| `frame-src` | `none` | `settings.py:291` |
| `object-src` | `none` | `settings.py:292` |
| Admin override | `'unsafe-eval'` added to script-src | `core/middleware.py:16` |

### Cookie Security

| Setting | Value | Location |
|---------|-------|----------|
| `SESSION_COOKIE_HTTPONLY` | True | `settings.py:80` |
| `CSRF_COOKIE_HTTPONLY` | True | `settings.py:81` |
| `SESSION_COOKIE_SAMESITE` | 'Lax' | `settings.py:82` |
| `CSRF_COOKIE_SAMESITE` | 'Lax' | `settings.py:83` |
| `SESSION_COOKIE_SECURE` | True (prod) | `settings.py:508` |
| `CSRF_COOKIE_SECURE` | True (prod) | `settings.py:509` |

### Production Security (`DEBUG=False`)

| Setting | Value | Location |
|---------|-------|----------|
| `SECURE_SSL_REDIRECT` | True | `settings.py:504` |
| `SECURE_HSTS_SECONDS` | 31536000 (1 year) | `settings.py:510` |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | True | `settings.py:511` |
| `SECURE_HSTS_PRELOAD` | True | `settings.py:512` |
| `X_FRAME_OPTIONS` | 'DENY' | `settings.py:514` |
| `SECURE_CONTENT_TYPE_NOSNIFF` | True | `settings.py:84` |

---

## 10. HTML Sanitization Pipeline

**Entry point:** `clean_post_body()` — `posts/utils/sanitization.py:165`

### Pipeline Steps

| Step | Function | Line | Purpose |
|------|----------|------|---------|
| 1 | Size check | 169 | Reject bodies > 500,000 chars |
| 2 | `looks_like_html()` | 172 | Skip pipeline for plain text |
| 3 | `bleach.clean()` | 175 | Strip disallowed tags/attributes |
| 4 | `_enforce_attribute_filter()` | 186 | html5lib-based pass: drops off-site media src/poster |
| 5 | `_add_heading_ids()` | 189 | Inject `id="<slug>"` on h2/h3/h4 |
| 6 | `_strip_external_media()` | 190 | Remove external media src (defense-in-depth) |
| 7 | `_enforce_noopener()` | 191 | Add `rel="noopener noreferrer"` to `target="_blank"` links |

### Allowed Tags (`posts/utils/sanitization.py:9`)

```python
ALLOWED_BODY_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's',
    'a', 'ul', 'ol', 'li', 'h2', 'h3', 'h4',
    'blockquote', 'pre', 'code',
    'img', 'video', 'audio', 'source',
    'div', 'figure', 'figcaption',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
]
```

### Allowed Attributes (`posts/utils/sanitization.py:17`)

```python
ALLOWED_BODY_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
    'code': ['class'], 'pre': ['class'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading', 'class'],
    'video': ['src', 'controls', 'preload', 'width', 'height', 'poster', 'class'],
    'audio': ['src', 'controls', 'preload', 'class'],
    'source': ['src', 'type'],
    'div': ['class'], 'figure': ['class'], 'figcaption': ['class'],
}
```

### Double Sanitization

1. **Save-time:** `Post.save()` calls `clean_post_body()` — `posts/models.py:266-271`
2. **Render-time:** `render_post_body` template filter calls `clean_post_body()` — `posts/templatetags/post_extras.py:94`

This is defense-in-depth. The save-time sanitization is the primary guard.

### Markdown Rendering Pipeline

**Entry point:** `render_markdown_body()` — `posts/utils/sanitization.py:190`

| Step | Function | Purpose |
|------|----------|---------|
| 1 | `markdown.markdown()` | Convert markdown to HTML (extensions: fenced_code, tables) |
| 2 | `clean_post_body()` | Sanitize the HTML through the standard bleach pipeline |

Used by `render_body_for_post` template filter when a post has `body_md_file` set.

---

## 11. Media Upload System

### Inline Media (Post Editor)

**Entry point:** `save_inline_media()` — `posts/utils/media.py:82`

**Validation pipeline** (`validate_inline_upload()` — `posts/utils/media.py:53`):

| Step | Check | Line |
|------|-------|------|
| 1 | Extension in ALLOWED_INLINE_EXTENSIONS | 54-55 |
| 2 | File size ≤ per-kind limit | 57-59 |
| 3 | MIME type in ALLOWED_MIME_TYPES | 62-64 |
| 4 | MIME prefix matches expected kind | 67-69 |
| 5 | Images: Pillow verify() for integrity | 72-78 |

**Size Limits:**
- Image: 10 MB
- Audio: 25 MB
- Video: 50 MB

**Storage:** UUID4 filename → `media/posts/inline/<uuid>.<ext>`

### Cover Image Processing

**Entry point:** `process_cover_image()` — `posts/image_processing.py:114`

Pipeline: Open → RGB → Centre-crop 16:9 → Resize 1200×675 → JPEG 85% quality

### Avatar Processing

**Entry point:** `process_avatar_image()` — `posts/image_processing.py:148`

Pipeline: Open → RGB → Centre-crop 1:1 → Resize 512×512 → JPEG 85% quality

### Attachment Validation

**Entry point:** `PostForm.clean_attachment()` — `posts/forms.py:105`

| Check | Limit | Line |
|-------|-------|------|
| Extension | 18 allowed types | `posts/forms.py:8-15` |
| File size | 100 MB | `posts/forms.py:17` |
| MIME type | 22 allowed types | `posts/forms.py:19-43` |

---

## 12. Template Tags & Filters

### post_extras (`posts/templatetags/post_extras.py`)

| Filter/Tag | Line | Usage | Description |
|------------|------|-------|-------------|
| `css_color` | 40 | `{{ value\|css_color }}` | Validates hex color; returns value or empty string |
| `url_replace` | 55 | `{% url_replace key=value %}` | Rebuilds query string with replaced/removed keys |
| `render_post_body` | 79 | `{{ post.body\|render_post_body }}` | Sanitizes + renders HTML; handles pre-escaped entities |
| `render_body_for_post` | 212 | `{{ post\|render_body_for_post }}` | Renders body_md_file (markdown→HTML) or falls back to render_post_body |
| `type_label` | 115 | `{{ post.post_type\|type_label }}` | Returns localised PostType name |
| `post_excerpt` | 130 | `{{ post.body\|post_excerpt:30 }}` | First N words as plain text with ellipsis |
| `table_of_contents` | 160 | `{{ post.body\|table_of_contents }}` | Generates `<ul class="toc-list">` from h2/h3 headings |

### panel_extras (`accounts/templatetags/panel_extras.py`)

| Filter | Line | Usage | Description |
|--------|------|-------|-------------|
| `in_field_group` | 23 | `{% if field_name\|in_field_group:"group1,group2" %}` | Checks if field_name is in comma-separated list |

### forum_extras (`forum/templatetags/forum_extras.py`)

| Filter | Line | Usage | Description |
|--------|------|-------|-------------|
| `forum_post_count` | 8 | `{{ user\|forum_post_count }}` | Count of non-deleted forum posts by user |
| `forum_thread_count` | 16 | `{{ board\|forum_thread_count }}` | Count of non-deleted threads in board |
| `render_forum_body` | 24 | `{{ post.body\|render_forum_body }}` | Render-time bleach sanitization for forum post bodies |

---

## 13. Templates

### Base Templates

| File | Lines | Purpose |
|------|-------|---------|
| `core/templates/core/base.html` | 163 | Master layout: HTML5, i18n, RTL, meta tags (OG, canonical, RSS), header, nav, footer, messages, scripts |
| `accounts/templates/accounts/auth_base.html` | — | Auth pages base (login, register, password reset) |
| `accounts/templates/accounts/panel_base.html` | — | Panel pages base (dashboard, edit, admin) |

### Error Pages

| File | Lines | Purpose |
|------|-------|---------|
| `core/templates/403.html` | 69 | Forbidden — uses `{% url 'home' %}` for i18n link |
| `core/templates/404.html` | 71 | Not found — uses `{% url 'home' %}` for i18n link |
| `core/templates/500.html` | 70 | Server error — uses `{{ request.path }}` for Try Again |

### Account Templates

| File | Lines | Purpose |
|------|-------|---------|
| `accounts/login.html` | 73 | Login form with password toggle, safe_next |
| `accounts/register.html` | 49 | Registration form with password toggle |
| `accounts/confirm_email_sent.html` | 21 | Post-registration info |
| `accounts/panel.html` | 104 | User dashboard |
| `accounts/edit_profile.html` | 54 | Edit user + profile form (field-by-field rendering) |
| `accounts/public_profile.html` | 75 | Public profile with published posts, visible certificates (i18n: name_fa shown when LANGUAGE_CODE=fa), staggered badge animation |

### Admin Templates

| File | Lines | Purpose |
|------|-------|---------|
| `accounts/admin_posts.html` | 152 | Post list: search, filters, bulk actions, sort |
| `accounts/admin_new_post.html` | 92 | New post form with dual-mode body |
| `accounts/admin_edit_post.html` | 88 | Edit post form (incl. old md file deletion) |
| `accounts/admin_delete_post.html` | 14 | Delete confirmation |
| `accounts/admin_post_taxonomy.html` | 266 | Category/subcategory/post type management |
| `accounts/admin_tags.html` | 51 | Tag management |
| `accounts/admin_users.html` | 78 | User management (superuser only) |
| `accounts/admin_certificates.html` | — | Certificate CRUD (superuser only) |
| `accounts/admin_grant_certificate.html` | — | Grant/revoke certificates (superuser only) |
| `accounts/user_certificates.html` | — | User's own certificates page |

### Forum Templates

| File | Lines | Purpose |
|------|-------|---------|
| `forum/index.html` | 65 | Board listing with stats and last post |
| `forum/board_detail.html` | 75 | Thread listing for a board, paginated (30/page) |
| `forum/thread_detail.html` | — | Thread with paginated posts (20/page), Quill.js reply form, mod actions |
| `forum/new_thread.html` | — | New thread form with Quill.js editor |
| `forum/edit_post.html` | — | Edit post form with Quill.js editor |
| `forum/new_board.html` | — | Board creation form (admin only) |
| `forum/_post_row.html` | 35 | Single post partial with render-time sanitization (render_forum_body) |

### Post Templates

| File | Lines | Purpose |
|------|-------|---------|
| `posts/post_list.html` | 112 | Paginated post browser with filter bar |
| `posts/post_detail.html` | 144 | Full article: TOC, related posts, sidebar |
| `posts/category_detail.html` | 75 | Category landing page |
| `posts/subcategory_detail.html` | 75 | Subcategory landing page |

### Partials

| File | Lines | Purpose |
|------|-------|---------|
| `posts/_post_card.html` | 41 | Reusable post card |
| `posts/_post_home_item.html` | 13 | Homepage news item |
| `posts/_post_archive_item.html` | 26 | Archive list item |
| `posts/_post_cover_thumb.html` | 5 | Cover thumbnail |
| `accounts/_panel_header.html` | 10 | Panel header (avatar, name) |
| `accounts/_post_editor_head.html` | 4 | Editor CSS includes |
| `accounts/_post_editor_scripts.html` | 9 | Editor JS: editor-messages.js, Quill, Tom Select, editor-utils, post-editor |
| `accounts/_post_body_field.html` | 106 | Dual-mode body: Write (Quill) or Upload Markdown, with radio toggle |
| `accounts/_post_cover_field.html` | 56 | Cover upload widget |
| `accounts/_post_media_fields.html` | 30 | Inline media fields |
| `comments/_comment_list.html` | 38 | Comment list + form (account-based) |
| `accounts/admin_comments.html` | 100 | Admin comments management |

### Search

| File | Lines | Purpose |
|------|-------|---------|
| `search/search.html` | 105 | Search form with filters + results |

---

## 14. Static Assets

### CSS

| File | Lines | Purpose |
|------|-------|---------|
| `core/static/core/style.css` | 17 | Import hub for 17 CSS partials |
| `core/static/core/css/_variables.css` | — | CSS custom properties (colors, spacing, typography) |
| `core/static/core/css/_base.css` | — | Reset, body, links, utilities |
| `core/static/core/css/_header.css` | — | Site header, branding, hamburger menu |
| `core/static/core/css/_nav.css` | — | Navigation bar, mobile menu |
| `core/static/core/css/_layout.css` | — | Main content, sidebar, footer |
| `core/static/core/css/_hero-buttons.css` | — | Hero section, CTA buttons |
| `core/static/core/css/_home.css` | — | Homepage sections |
| `core/static/core/css/_article.css` | — | Article detail, body content |
| `core/static/core/css/_archive-cards.css` | — | Post cards, archive lists |
| `core/static/core/css/_search.css` | — | Search form and results |
| `core/static/core/css/_panel.css` | — | User panel, dashboard, forms |
| `core/static/core/css/_taxonomy.css` | — | Category/subcategory/tag management |
| `core/static/core/css/_error-pages.css` | — | 404, 403, 500 pages |
| `core/static/core/css/_comments.css` | — | Comment section styles |
| `core/static/core/css/_admin-utils.css` | — | Admin utility classes |
| `core/static/core/css/_forum.css` | — | Forum components |
| `core/static/core/css/_responsive.css` | — | Mobile breakpoints |
| `core/static/core/rtl.css` | 45 | RTL overrides for Persian; Vazirmatn Light (weight 300) for `html[lang="fa"]` body and headings |
| `core/static/core/post-editor.css` | 482 | Quill editor overrides, media embed, cover upload |
| `core/static/core/local-fonts.css` | 97 | @font-face for Source Sans 3 + Vazirmatn |

### Certificate Badge Styles (`core/static/core/style.css`)

- `.profile-certificates` — section container with top margin
- `.cert-badge-row` — flex-wrap row, 0.6rem gap
- `.cert-badge` — inline-flex pill: white bg, 2px border + 4px left accent border, hover shadow
- `.cert-badge-dot` — 10px colored circle (fallback when no icon)
- `.cert-badge-icon` — 24px round image
- `.cert-badge-name` — certificate name text
- Staggered entrance animation: `@keyframes cert-badge-in` (fade + slide-up 8px), 80ms delay per badge via CSS `--i` custom property
- Animation disabled under `prefers-reduced-motion: reduce`
- Public profile shows `name_fa` when `LANGUAGE_CODE == 'fa'`

### JavaScript

| File | Lines | Purpose |
|------|-------|---------|
| `core/static/core/main.js` | 237 | Hamburger menu, active nav, smooth scroll, back-to-top, message dismiss, submit lock, site alert, auto-submit |
| `core/static/core/post-editor.js` | 530 | Quill init, Tom Select, media upload, drag-drop, cover upload |
| `core/static/core/editor-utils.js` | — | Shared utilities: CSRF token, HTML escaping, media upload (i18n via `window.EditorMessages`), media HTML builders |
| `accounts/static/accounts/panel.js` | 149 | Password toggle, login/register UX, bulk actions, taxonomy edit toggle |
| `accounts/static/accounts/post-editor-panel.js` | 111 | Slug auto-gen, dynamic subcategory AJAX (loading/error strings via data attributes) |
| `accounts/static/accounts/body-mode-toggle.js` | 45 | Radio toggle between Write/Upload modes, section show/hide, body clear on submit |
| `accounts/static/accounts/editor-messages.js` | — | Reads translated strings from #editor-config data attributes, sets window.EditorMessages |
| `accounts/static/accounts/taxonomy.js` | 61 | Tab highlighting, color picker sync |
| `forum/static/forum/forum-editor.js` | — | Quill.js init with toolbar + image upload for forum forms |

### Vendor

| File | Purpose |
|------|---------|
| `core/static/vendor/quill.*` | Quill.js rich text editor |
| `core/static/vendor/tom-select.*` | Tom Select searchable dropdowns |

---

## 15. Settings

### Critical Settings (`myproject/settings.py`)

| Setting | Value | Line |
|---------|-------|------|
| `SECRET_KEY` | From env (RuntimeError if empty) | 49 |
| `DEBUG` | From env (default=True) | 56 |
| `ALLOWED_HOSTS` | From env | 60 |
| `ROOT_URLCONF` | 'myproject.urls' | 140 |
| `AUTH_USER_MODEL` | 'accounts.CustomUser' | 232 |
| `LOGIN_URL` | 'accounts:login' | 233 |
| `LOGIN_REDIRECT_URL` | 'accounts:panel' | 236 |
| `LOGOUT_REDIRECT_URL` | 'home' | 239 |
| `DEFAULT_AUTO_FIELD` | 'django.db.models.BigAutoField' | 426 |

### Database (`myproject/settings.py:186-210`)

- Production: MySQL via `DATABASE_URL` env var
- Development: SQLite fallback
- Test: SQLite in-memory (auto-created/destroyed)

### Cache (`myproject/settings.py:219-264`)

- Production: Redis via `REDIS_URL` env var (shared across workers)
- Development: LocMemCache (per-process fallback)
- Rate limits are NOT shared across Gunicorn workers without Redis
- Context processor cache TTL: 300s (Redis) or 60s (LocMemCache)

### Installed Apps (`myproject/settings.py:90-110`)

```python
INSTALLED_APPS = [
    'axes',
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
    'core',
    'posts',
    'accounts',
    'search',
    'comments',
    'forum',
]
```

### Axes (Brute-force) Settings (`myproject/settings.py:260-276`)

| Setting | Value |
|---------|-------|
| `AXES_FAILURE_LIMIT` | 5 |
| `AXES_COOLOFF_TIME` | timedelta(hours=1) |
| `AXES_RESET_ON_SUCCESS` | True |
| `AXES_LOCKOUT_PARAMETERS` | ["ip_address", "username"] |
| `AXES_IPWARE_PROXY_COUNT` | 1 |
| `AXES_ENABLE_ADMIN` | False |

### Logging (`myproject/settings.py:326-375`)

| Logger | File | Purpose |
|--------|------|---------|
| `axes` | `logs/axes.log` | Brute-force attempts |
| `audit` | `logs/audit.log` | Security events (login, logout, CRUD) |
| `accounts.email_verification` | `logs/email_confirmation.log` | Email confirmation flow |

### Settings Runtime Detection (`myproject/settings.py:42-47`)

`_RUNNING_TESTS` is defined at the top of `settings.py` (after imports) and
referenced by the CACHE and STORAGES sections. Must remain at the top to
avoid NameError on reordering.

```python
_RUNNING_TESTS = (
    'test' in sys.argv
    or 'pytest' in sys.modules
    or any('pytest' in arg for arg in sys.argv)
)
```

---

## 16. Database Schema & Indexes

### Migrations

| Migration | App | Purpose |
|-----------|-----|---------|
| `posts.0001_initial` | posts | Initial schema |
| `posts.0008_add_body_md_file` | posts | Add `body_md_file` FileField to Post |

### Post Indexes (`posts/models.py:239-245`)

| Index | Fields | Purpose |
|-------|--------|---------|
| `post_pubdate_visible_idx` | `-pub_date`, `is_visible` | Most queries filter by visibility + date |
| `post_category_visible_idx` | `category`, `is_visible` | Category list view |
| `post_type_visible_idx` | `post_type`, `is_visible` | Post type filtering |
| `post_title_idx` | `title` | Title search |
| `post_author_idx` | `author_name` | Author search |

### Constraints

| Model | Constraint | Location |
|-------|-----------|----------|
| `Subcategory` | UniqueConstraint(category, slug) | `posts/models.py:95-96` |
| `CustomUser.email` | unique=True | `accounts/models.py:54` |

---

## 17. Caching Strategy

### Context Processor Cache

- **Key:** `global_nav_context` — `core/context_processors.py:46`
- **TTL:** 300 seconds (5 min) — `core/context_processors.py:47`
- **Backend:** LocMemCache
- **Stampede prevention:** `cache.add()` — `core/context_processors.py:74`

### Rate Limit Cache Keys

| Action | Key Pattern | TTL |
|--------|-------------|-----|
| `register` | `register_<ip>` | 300s |
| `resend_confirm` | `resend_confirm_<ip>` | 3600s |
| `email_confirm` | `email_confirm_<ip>` | 3600s |
| `pw_reset` | `pw_reset_<ip>` | 3600s |
| `search` | `search_<ip>` | 60s |
| `comment` | `comment_<ip>` | 300s |

---

## 18. Testing

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `accounts/tests.py` | 160 | Auth, admin, forms, models, security, rate limiting, XSS |
| `posts/tests.py` | 107 | Models, views, sanitization, media, feeds, sitemaps, markdown mode |
| `core/tests.py` | 69 | Views, middleware, context processors, CSS, templates |
| `search/tests.py` | 126 | Search, pagination, rate limiting, date filtering |
| `comments/tests.py` | 41 | Model, form, views, admin, visibility, account-based, per-post mgmt |
| `forum/tests.py` | 73 | Models, views, forms, template tags, upload media |
| **Total** | **450** | |

### Running Tests

```bash
python manage.py test                    # All 450 tests
python manage.py test accounts           # 160 tests
python manage.py test posts              # 107 tests
python manage.py test core               # 69 tests
python manage.py test search             # 126 tests
python manage.py test comments           # 41 tests
python manage.py test forum              # 73 tests
python manage.py test accounts.LoginViewTests  # Specific test class
```

### Test Infrastructure

- Database: SQLite in-memory (auto-created/destroyed)
- Static files: `StaticFilesStorage` (no collectstatic needed)
- No external services required

---

## 19. Deployment

### Gunicorn (`gunicorn.conf.py`)

| Setting | Value | Line |
|---------|-------|------|
| `bind` | `127.0.0.1:8000` | 28 |
| `workers` | `CPU_COUNT * 2 + 1` | 35 |
| `worker_class` | `sync` | 37 |
| `timeout` | `120` | 42 |
| `keepalive` | `5` | 44 |
| `max_requests` | `1000` | 49 |
| `max_requests_jitter` | `100` | 52 |
| `preload_app` | `True` | 75 |
| `server_header` | `False` | 73 |

### Nginx Config (recommended)

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /static/ {
        alias /path/to/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /path/to/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Production Checklist

- [ ] Set `DEBUG=False` in .env
- [ ] Set `SECRET_KEY` to a strong random value
- [ ] Set `ALLOWED_HOSTS` to your domain(s)
- [ ] Configure `DATABASE_URL` for MySQL
- [ ] Configure email settings (EMAIL_HOST, etc.)
- [ ] Run `python manage.py migrate`
- [ ] Run `python manage.py collectstatic`
- [ ] Configure Nginx as reverse proxy
- [ ] Set up SSL certificates
- [ ] Configure log rotation for logs/axes.log, logs/audit.log

---

## 20. File Reference Index

### Python Files (by size)

| File | Lines | Purpose |
|------|-------|---------|
| `accounts/tests.py` | 1259 | Account tests |
| `posts/tests.py` | 865 | Post tests (incl. MarkdownBodyModeTests) |
| `core/tests.py` | 613 | Core tests |
| `myproject/settings.py` | 465 | Django configuration |
| `accounts/views/admin.py` | 335 | Admin panel views |
| `posts/models.py` | 328 | Post/Category/Tag models (+ body_md_file) |
| `accounts/forms.py` | 186 | Auth/profile forms |
| `posts/templatetags/post_extras.py` | 229 | Template filters (incl. render_body_for_post) |
| `posts/views.py` | 220 | Post views |
| `posts/utils/sanitization.py` | 196 | HTML sanitization + render_markdown_body() |
| `accounts/models.py` | 148 | User/AuditLog models |
| `posts/image_processing.py` | 146 | Image processing |
| `posts/forms.py` | 236 | Post form (+ body_mode toggle, markdown validation) |
| `search/views.py` | 140 | Search view |
| `accounts/views/auth.py` | 139 | Auth views |
| `accounts/views/admin/__init__.py` | — | Re-exports all admin views |
| `accounts/views/admin/_posts.py` | — | Post CRUD, media upload, bulk actions |
| `accounts/views/admin/_taxonomy.py` | — | Category/subcategory/post type CRUD |
| `accounts/views/admin/_comments.py` | — | Comment management |
| `accounts/views/admin/_users.py` | — | User management (superuser only) |
| `accounts/views/admin/_certificates.py` | — | Certificate CRUD + grants |
| `search/tests.py` | 126 | Search tests |
| `accounts/utils.py` | 89 | Utilities |
| `core/context_processors.py` | 71 | Context processor |
| `posts/utils/media.py` | 71 | Media validation |
| `core/middleware.py` | 83 | CSP middleware |
| `accounts/email_verification.py` | 94 | Email verification |
| `gunicorn.conf.py` | 65 | Gunicorn config |
| `accounts/urls.py` | 63 | Account URLs |
| `core/views.py` | 54 | Core views |
| `posts/feeds.py` | 54 | RSS feed |
| `accounts/admin.py` | 54 | Admin registration |
| `posts/admin.py` | 51 | Admin registration |
| `accounts/views/panel.py` | 41 | Panel views |
| `posts/urls.py` | 34 | Post URLs |
| `posts/sitemaps.py` | 29 | Sitemaps |
| `accounts/signals.py` | 25 | Signals |
| `accounts/otp.py` | 58 | OTP (inactive) |
| `core/urls.py` | 22 | Core URLs |
| `posts/utils/__init__.py` | 19 | Utils exports |
| `accounts/views/__init__.py` | 16 | View exports |
| `manage.py` | 18 | Management command |
| `core/admin.py` | 18 | Admin registration |
| `myproject/wsgi.py` | 17 | WSGI entry |

### Template Files (by size)

| File | Lines |
|------|-------|
| `accounts/admin_post_taxonomy.html` | 266 |
| `core/base.html` | 163 |
| `accounts/admin_posts.html` | 152 |
| `posts/post_detail.html` | 144 |
| `posts/post_list.html` | 112 |
| `search/search.html` | 105 |
| `accounts/panel.html` | 104 |
| `accounts/admin_edit_post.html` | 85 |
| `accounts/admin_new_post.html` | 92 |
| `accounts/admin_users.html` | 78 |
| `posts/category_detail.html` | 75 |
| `posts/subcategory_detail.html` | 75 |
| `accounts/login.html` | 73 |
| `core/home.html` | 71 |
| `404.html` | 71 |
| `500.html` | 70 |
| `403.html` | 69 |

### Static Files (by size)

| File | Lines |
|------|-------|
| `core/post-editor.css` | 482 |
| `core/post-editor.js` | 530 |
| `accounts/panel.js` | 149 |
| `core/main.js` | 141 |
| `accounts/post-editor-panel.js` | 111 |
| `core/local-fonts.css` | 97 |
| `accounts/taxonomy.js` | 61 |
| `core/rtl.css` | 45 |
| `core/editor-utils.js` | — |

---

*Documentation generated for OpenSrcPersian Django 6.0 CMS.*
