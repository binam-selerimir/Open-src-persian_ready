"""
core/models.py
==============
Defines the Page model — simple flat content pages (About, FAQ, etc.)
that can optionally appear in the site navigation bar.

Usage
-----
* Pages are created and edited via the Django admin (/admin/core/page/).
* seed_data.py management command creates starter pages on first run.
* The global_context context processor (core/context_processors.py)
  injects `nav_pages` (show_in_nav=True) into every template.
* Individual pages are rendered at /<lang>/page/<slug>/ by core/views.page_detail.
"""

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Page(models.Model):
    """
    A simple flat content page with bilingual title and body.

    title_en / title_fa and body_en / body_fa store the English and Persian
    versions. The ``title`` and ``body`` properties return the correct
    language version based on the current thread's language.

    show_in_nav  – when True, the page link appears in the navigation bar.
    nav_order    – controls the display order among nav pages (lower = left/first).
    body         – plain text rendered via |linebreaks in page_detail.html.
                   SECURITY: do NOT render with |safe — the body is admin-editable
                   and |linebreaks escapes HTML before converting newlines.
    """

    title_en = models.CharField(max_length=255)
    title_fa = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    body_en = models.TextField()
    body_fa = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Controls whether this page appears as a link in the site navigation.
    show_in_nav = models.BooleanField(default=False)
    # Display order in the nav bar (0 = first/leftmost).
    nav_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['nav_order', 'title_en']
        verbose_name = _('Page')
        verbose_name_plural = _('Pages')

    def __str__(self):
        return self.title

    @property
    def title(self):
        """Return the title in the current language, falling back to English."""
        from django.utils import translation
        lang = translation.get_language()
        if lang == 'fa' and self.title_fa:
            return self.title_fa
        return self.title_en

    @property
    def body(self):
        """Return the body in the current language, falling back to English."""
        from django.utils import translation
        lang = translation.get_language()
        if lang == 'fa' and self.body_fa:
            return self.body_fa
        return self.body_en

    def get_absolute_url(self):
        """Return the canonical URL: /<lang>/page/<slug>/"""
        return reverse('page_detail', kwargs={'slug': self.slug})


class SiteAlert(models.Model):
    """
    A site-wide announcement banner shown at the top of every page.

    Bilingual: title_en/title_fa and message_en/message_fa store the
    English and Persian versions. The context processor selects the
    correct pair based on the current language.

    Only one active, non-expired alert is shown at a time.
    Users can dismiss the alert via a cookie (alert_dismissed_<id>).
    """

    title_en = models.CharField(_('Title (English)'), max_length=200)
    title_fa = models.CharField(_('Title (Persian)'), max_length=200, blank=True)
    message_en = models.TextField(_('Message (English)'))
    message_fa = models.TextField(_('Message (Persian)'), blank=True)
    is_active = models.BooleanField(_('Active'), default=True)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    expires_at = models.DateTimeField(
        _('Expires at'), null=True, blank=True,
        help_text=_('Optional. Leave blank for no expiration.'),
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Site Alert')
        verbose_name_plural = _('Site Alerts')

    def __str__(self):
        return self.title_en

    def is_visible(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    def get_localised_title(self, lang=None):
        """Return the title in the given language, falling back to English."""
        from django.utils import translation
        lang = lang or translation.get_language()
        if lang == 'fa' and self.title_fa:
            return self.title_fa
        return self.title_en

    def get_localised_message(self, lang=None):
        """Return the message in the given language, falling back to English."""
        from django.utils import translation
        lang = lang or translation.get_language()
        if lang == 'fa' and self.message_fa:
            return self.message_fa
        return self.message_en
