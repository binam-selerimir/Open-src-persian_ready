"""
accounts/email_verification.py
================================
Email-confirmation workflow used at registration time.

How it works
------------
1. On successful registration, ``send_confirmation_email`` generates a signed
   token containing the new user's PK using Django's TimestampSigner.
2. The raw signed token (format ``value:timestamp:signature``) is
   **base64url-encoded** so that the URL contains no ``:`` characters that
   email clients or browsers could mangle.
3. An email is sent to the user with a confirmation URL that embeds the
   URL-safe token.
4. When the user clicks the link, ``verify_url_token`` decodes the
   base64url token and validates the embedded signature.
5. If the token is valid and not expired (< 48 h), the user's ``is_active``
   flag is set to True and they can log in.

Security notes
--------------
* TimestampSigner adds an HMAC signature derived from SECRET_KEY and the
  provided salt, so tokens cannot be forged or reused across sites.
* Tokens expire after 48 hours; expired or tampered tokens return None.
* A rate-limit on the confirmation endpoint (max 10 tries/IP/hour) prevents
  automated probing of the token space.
* base64url-encoding prevents email clients from stripping or breaking on
  ``:`` characters in the URL path.
"""

import base64
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse
from django.utils.translation import gettext as _

logger = logging.getLogger('accounts.email_verification')

_SIGNER = TimestampSigner(salt='accounts.email-confirm')
_TOKEN_MAX_AGE = 60 * 60 * 48  # 48 hours


def _raw_sign(user_id):
    return _SIGNER.sign(str(user_id))


def _raw_unsign(signed_token):
    return int(_SIGNER.unsign(signed_token, max_age=_TOKEN_MAX_AGE))


def _b64url_encode(raw_token):
    return base64.urlsafe_b64encode(raw_token.encode('utf-8')).rstrip(b'=').decode('ascii')


def _b64url_decode(url_token):
    padded = url_token + '=' * (-len(url_token) % 4)
    return base64.urlsafe_b64decode(padded).decode('utf-8')


def make_url_token(user_id):
    raw = _raw_sign(user_id)
    url_token = _b64url_encode(raw)
    return url_token


def verify_url_token(url_token):
    try:
        raw = _b64url_decode(url_token)
        result = int(_SIGNER.unsign(raw, max_age=_TOKEN_MAX_AGE))
        return result
    except SignatureExpired as e:
        logger.warning('Token expired: %s', e)
        return None
    except BadSignature as e:
        logger.warning('Token bad signature: %s', e)
        return None
    except Exception as e:
        logger.warning('Token error: %s', e)
        return None


def send_confirmation_email(request, user):
    url_token = make_url_token(user.pk)
    confirm_url = request.build_absolute_uri(
        reverse('accounts:confirm_email', kwargs={'token': url_token})
    )
    logger.info('Confirmation URL for %s: %s', user.username, confirm_url)
    subject = _('Confirm your OpenSrc Persian account')

    plain_message = (
        'Hello {username},\n\n'
        'Thank you for registering. Please confirm your email address by visiting the link below:\n\n'
        '{url}\n\n'
        'This link expires in 48 hours.\n\n'
        'If you did not create this account, you can ignore this email.'
    ).format(username=user.username, url=confirm_url)

    html_message = (
        '<!DOCTYPE html>'
        '<html><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:0;background:#f8f7f4;font-family:Arial,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f7f4;padding:40px 20px;">'
        '<tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:3px;overflow:hidden;border:1px solid #d0cdc8;">'
        '<tr><td style="background:#001a33;padding:24px 32px;border-bottom:3px solid #ffcc00;">'
        '<span style="color:#ffffff;font-size:22px;font-weight:600;">'
        'Open<span style="color:#ffcc00;">Src</span> Persian</span>'
        '</td></tr>'
        '<tr><td style="padding:32px;">'
        '<p style="color:#1a1917;font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'Hello <strong>{username}</strong>,</p>'
        '<p style="color:#1a1917;font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'Thank you for registering. Please confirm your email address by '
        'clicking the button below:</p>'
        '<p style="text-align:center;margin:28px 0;">'
        '<a href="{url}" style="display:inline-block;background:#001a33;color:#ffffff;'
        'font-size:16px;font-weight:600;text-decoration:none;padding:14px 36px;'
        'border-radius:3px;">Confirm Email</a></p>'
        '<p style="color:#5a5754;font-size:14px;line-height:1.7;margin:0 0 8px;">'
        'Or copy this link:</p>'
        '<p style="color:#004a99;font-size:13px;word-break:break-all;margin:0 0 24px;">'
        '<a href="{url}" style="color:#004a99;">{url}</a></p>'
        '<hr style="border:none;border-top:1px solid #d0cdc8;margin:24px 0;">'
        '<p style="color:#5a5754;font-size:13px;line-height:1.6;margin:0;">'
        'This link expires in 48 hours. If you did not create this account, '
        'you can ignore this email.</p>'
        '</td></tr>'
        '<tr><td style="background:#001a33;padding:16px 32px;">'
        '<p style="color:#5a80a0;font-size:12px;margin:0;text-align:center;">'
        '&copy; OpenSrc Persian</p>'
        '</td></tr>'
        '</table></td></tr></table>'
        '</body></html>'
    ).format(username=user.username, url=confirm_url)

    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
        html_message=html_message,
    )
