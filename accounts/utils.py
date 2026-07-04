"""
accounts/utils.py
=================
Shared helpers used across the accounts app:

  get_client_ip(request)  – extract the real client IP from request metadata,
                            taking a single trusted reverse proxy into account.

  audit(request, action, description)
                          – write a row to the AuditLog model *and* emit a
                            structured log line to the "audit" file logger.

  check_rate_limit(request, action, limit, ttl)
                          – per-IP rate limiter backed by Django's cache;
                            returns True if allowed, False if over limit.
"""

from .models import AuditLog
import ipaddress
import logging

from django.core.cache import cache


# Logger instance bound to the "audit" logger configured in settings.py.
# Its handler writes to logs/audit.log.
audit_logger = logging.getLogger("audit")


def _is_valid_ip(ip_str):
    """Return True if ip_str is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def get_client_ip(request):
    """
    Return the client's real IP address.

    DEPLOYMENT ASSUMPTION: exactly one trusted reverse proxy (e.g. Nginx or
    Gunicorn behind a single load-balancer) sits in front of Django.  Under
    this assumption, the *rightmost* entry in X-Forwarded-For is the IP
    appended by that trusted proxy and therefore reflects the real client —
    the leftmost entries are client-controlled and must not be trusted.

    SECURITY: The extracted IP is validated as a valid IP address format.
    If the X-Forwarded-For header contains non-IP values (indicating header
    injection or spoofing), we fall back to REMOTE_ADDR. This prevents
    attackers from manipulating rate-limit cache keys by injecting arbitrary
    strings into the header.

    If this deployment ever adds a CDN or second proxy layer, revisit this
    function: the rightmost hop will then be the CDN's IP, making rate-
    limiting effectively per-CDN rather than per-client.  In that case,
    configure django-ipware or a similar library with an explicit
    TRUSTED_PROXY_LIST and use num_proxies accordingly.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        # Split the header and take the last (rightmost) IP added by our
        # trusted proxy — the entries to the left are client-supplied.
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        if ips:
            candidate = ips[-1]
            # Validate that the extracted value is actually an IP address.
            # Reject spoofed/injected header values (e.g. "1.2.3.4, evil<script>")
            # by falling back to REMOTE_ADDR.
            if _is_valid_ip(candidate):
                return candidate
            # Log suspicious header values for security monitoring.
            audit_logger.warning(
                "Invalid X-Forwarded-For value rejected: %s (from %s)",
                candidate, request.META.get("REMOTE_ADDR", "unknown"),
            )
    # Fallback: REMOTE_ADDR is the direct connection IP, reliable when
    # there is no proxy or when AXES_IPWARE_PROXY_COUNT=0.
    # Return '127.0.0.1' if REMOTE_ADDR is missing (misconfigured server)
    # to prevent rate-limit cache keys from colliding on None.
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def audit(request, action, description=""):
    """
    Record a security/content-management event in two places:

    1. AuditLog database row — persisted, queryable via Django admin.
    2. audit_logger INFO line — written to logs/audit.log for real-time
       monitoring and log-shipping to external tools (e.g. Splunk, Grafana).

    Parameters
    ----------
    request     : Django HttpRequest — used to extract user and IP.
    action      : str — one of AuditLog.ACTIONS (e.g. "POST_CREATE").
    description : str — optional human-readable context message.
    """
    ip = get_client_ip(request)

    # Persist the event to the database; user is NULL for anonymous actions.
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        description=description,
        ip_address=ip,
    )

    # Emit a structured log line: user | action | ip | description
    audit_logger.info(
        "%s | %s | %s | %s",
        request.user if request.user.is_authenticated else "Anonymous",
        action,
        ip,
        description,
    )


def check_rate_limit(request, action, limit, ttl=3600, increment=True):
    """
    Check and optionally increment a per-IP rate limit counter.

    Returns True if the request is allowed (under limit), False if over limit.
    The counter is stored in Django's cache and expires after ``ttl`` seconds.
    When ``increment=False``, the counter is only read (not incremented),
    which is useful for views where only failed attempts should count.
    """
    ip = get_client_ip(request)
    cache_key = f'{action}_{ip}'
    attempts = cache.get(cache_key, 0)
    if attempts >= limit:
        return False
    if increment:
        cache.set(cache_key, attempts + 1, timeout=ttl)
    return True
