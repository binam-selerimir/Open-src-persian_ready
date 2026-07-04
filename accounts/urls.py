"""
accounts/urls.py
================
URL patterns for the accounts application (namespace: 'accounts').

Auth endpoints (no login required)
-----------------------------------
login/                       – login form (login_view)
logout/                      – POST-only logout (logout_view)
register/                    – new account registration (register_view)
confirm-email/sent/          – confirmation-email-sent info page
confirm-email/<token>/       – email confirmation link handler

User panel (login required)
----------------------------
panel/                       – dashboard / profile overview
panel/edit-profile/          – edit user + profile fields
panel/upload-media/          – inline media upload endpoint (returns JSON URL)

Admin panel (login + is_site_admin required)
--------------------------------------------
panel/new-post/              – create a new post
panel/posts/                 – post list with search, filter, sort, bulk actions
panel/posts/<pk>/edit/       – edit an existing post
panel/posts/<pk>/delete/     – delete a post (confirmation page)
panel/taxonomy/              – manage categories, subcategories, post types
panel/tags/                  – manage tags
panel/users/                 – user management (is_site_admin only)

Public
------
profile/<username>/          – public user profile page
"""

from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # --- Authentication ------------------------------------------------------
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    # Shown after registration; instructs the user to check their inbox.
    path('confirm-email/sent/', views.confirm_email_sent, name='confirm_email_sent'),
    # Allow users to request a new confirmation email.
    path('confirm-email/resend/', views.resend_confirmation_email, name='resend_confirmation'),
    # Token is a base64url-encoded TimestampSigner-signed string.
    # The raw token contains ':' characters (format: value:timestamp:signature)
    # which email clients mangle, so we base64url-encode it for the URL.
    path('confirm-email/<str:token>/', views.confirm_email_view, name='confirm_email'),

    # --- User panel ----------------------------------------------------------
    path('panel/', views.panel_dashboard, name='panel'),
    path('panel/edit-profile/', views.edit_profile, name='edit_profile'),
    # Returns {url, type, name} JSON; used by the post editor for inline media.
    path('panel/upload-media/', views.upload_post_media, name='upload_post_media'),

    # --- Admin panel – posts -------------------------------------------------
    path('panel/new-post/', views.admin_new_post, name='admin_new_post'),
    path('panel/posts/', views.admin_posts, name='admin_posts'),
    path('panel/posts/<int:pk>/edit/', views.admin_edit_post, name='admin_edit_post'),
    path('panel/posts/<int:pk>/delete/', views.admin_delete_post, name='admin_delete_post'),

    # --- Admin panel – taxonomy & config ------------------------------------
    path('panel/taxonomy/', views.admin_post_taxonomy, name='admin_post_taxonomy'),
    path('panel/tags/', views.admin_tags, name='admin_tags'),
    # Restricted to is_site_admin (not just is_staff).
    path('panel/users/', views.admin_users, name='admin_users'),
    # --- Admin panel – comments ----------------------------------------------
    path('panel/comments/', views.admin_comments, name='admin_comments'),

    # --- Certificate management (superuser) ----------------------------------
    path('panel/certificates/', views.admin_certificates, name='admin_certificates'),
    path('panel/certificates/grant/', views.admin_grant_certificate, name='admin_grant_certificate'),
    # --- User's own certificates ---------------------------------------------
    path('panel/my-certificates/', views.user_certificates, name='user_certificates'),

    # --- Public --------------------------------------------------------------
    path('profile/<str:username>/', views.public_profile, name='public_profile'),
]
