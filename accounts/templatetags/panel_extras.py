"""
accounts/templatetags/panel_extras.py
=======================================
Custom template filter for the admin panel templates.

in_field_group
--------------
Used in panel form templates to determine whether a form field name belongs
to a logical display group, allowing the template to conditionally wrap
related fields in a shared container or style.

Usage:
    {% if field.name|in_field_group:"title,slug,category" %}
        {# Render this field inside the "metadata" section #}
    {% endif %}
"""

from django import template

register = template.Library()


@register.filter
def in_field_group(field_name, group):
    """
    Return True if field_name is in a comma-separated list of names.

    Parameters
    ----------
    field_name : str  — the name of the form field to check.
    group      : str  — comma-separated list of field names, e.g. "title,slug,category".

    Example:
        {{ "title"|in_field_group:"title,slug" }}   →  True
        {{ "body"|in_field_group:"title,slug" }}    →  False
    """
    names = [n.strip() for n in group.split(',')]
    return field_name in names
