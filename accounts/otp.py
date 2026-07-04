"""
accounts/otp.py
================
TOTP / OTP support — NOT YET ACTIVE.

This module contains helpers for generating and verifying TOTP codes using
pyotp, but two-factor authentication is not yet wired into the login flow.

How to enable 2FA when ready
-----------------------------
  1. Add `otp_secret` (CharField, blank=True) and `otp_enabled` (BooleanField,
     default=False) to CustomUser and generate a migration.
  2. Create a setup view that calls generate_secret() + generate_qr() and
     saves the secret to the user after a successful first verification.
  3. Add a second step to login_view that calls verify_code() when
     user.otp_enabled is True.
  4. Add an OTP migration.

Until those steps are complete, none of the functions below are called by
any view, URL, or signal.
"""

import io
import base64

import pyotp
import qrcode


def generate_secret():
    """Generate a new random TOTP secret in Base32 format.

    The returned string should be stored on CustomUser.otp_secret
    and never logged or exposed in plain text.
    """
    return pyotp.random_base32()


def generate_qr(secret, username):
    """
    Generate a QR-code PNG for the user to scan with an authenticator app.

    Returns the image as a base64-encoded string so it can be embedded
    directly in an HTML <img src="data:image/png;base64,..."> tag.

    Parameters
    ----------
    secret   : str  — the Base32 TOTP secret from generate_secret().
    username : str  — shown as the account name inside the authenticator app.
    """
    totp = pyotp.TOTP(secret)
    # provisioning_uri builds the otpauth:// URI that authenticator apps parse.
    uri = totp.provisioning_uri(
        name=username,
        issuer_name="OpenSrcPersian",   # Displayed in the authenticator app.
    )
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    # Return base64 so the caller can embed it without writing a temp file.
    return base64.b64encode(buffer.getvalue()).decode()


def verify_code(secret, code):
    """
    Verify a 6-digit TOTP code against the stored secret.

    pyotp.TOTP.verify() accepts codes from the current window and one
    window in each direction (30-second tolerance) to handle clock drift.

    Returns True if the code is valid, False otherwise.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code)
