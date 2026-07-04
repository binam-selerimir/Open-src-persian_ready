"""Admin views package — split into focused modules.

Re-exports all public symbols so existing URL imports continue to work.
"""

from ._common import _safe_int, _admin_login_required
from ._posts import (
    upload_post_media, admin_new_post, admin_posts,
    admin_edit_post, admin_delete_post,
)
from ._taxonomy import admin_post_taxonomy, admin_tags
from ._comments import admin_comments
from ._users import admin_users
from ._certificates import admin_certificates, admin_grant_certificate

__all__ = [
    '_safe_int', '_admin_login_required',
    'upload_post_media', 'admin_new_post', 'admin_posts',
    'admin_edit_post', 'admin_delete_post',
    'admin_post_taxonomy', 'admin_tags',
    'admin_comments',
    'admin_users',
    'admin_certificates', 'admin_grant_certificate',
]
