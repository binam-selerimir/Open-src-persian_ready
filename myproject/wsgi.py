"""
myproject/wsgi.py
=================
WSGI entry point for the OpenSrcPersian Django application.

This module exposes the WSGI callable as 'application', which is the
standard interface between a WSGI server (Gunicorn, uWSGI, mod_wsgi)
and the Django application.

The DJANGO_SETTINGS_MODULE environment variable points to the settings
module.  This default is used by Gunicorn and local development servers.
For alternative environments (e.g. staging), override this variable
in the process environment before starting the server.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Build the WSGI application from Django's settings.
application = get_wsgi_application()
