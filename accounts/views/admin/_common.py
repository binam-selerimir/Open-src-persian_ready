"""Shared decorators and utilities for admin views."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def _safe_int(value, default=0):
    """Safely convert value to int, returning default on failure."""
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _admin_login_required(view_func):
    """Decorator: requires login + (is_site_admin or is_staff)."""
    @wraps(view_func)
    @login_required(login_url='accounts:login')
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_site_admin or request.user.is_staff):
            return render(request, '403.html', status=403)
        return view_func(request, *args, **kwargs)
    return wrapper
