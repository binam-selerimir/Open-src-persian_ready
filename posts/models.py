"""
posts/models.py
===============
Database models for all content objects in the platform:

  Category    – top-level content grouping (e.g. "Technology").
  Subcategory – optional child grouping scoped to a Category (e.g. "Software").
  PostType    – content format tag with a display accent colour (e.g. "Translation").
  Tag         – free-form labels applied to posts via ManyToManyField.
  Post        – the primary content model: article/news item with title, body,
                cover image, optional attachment, authorship metadata, and
                visibility control.

Design notes
------------
* Both Category and PostType use PROTECT on delete to prevent accidental
  data loss from posts that reference them.
* Subcategory uses SET_NULL so a post is not lost if its subcategory is removed.
* The Post.body field stores HTML produced by the WYSIWYG editor in
  core/static/core/post-editor.js; it is sanitised on save via clean_post_body()
  in posts/utils.py.
* Post.cover_image is processed by posts/image_processing.py (resized to 1200×675 JPEG)
  before being stored.
"""

from functools import cached_property

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Validator shared by PostType.accent_color to enforce a valid CSS hex colour.
_hex_color_validator = RegexValidator(
    regex=r'^#[0-9a-fA-F]{6}$',
    message=_('Enter a valid hex colour (e.g. #ffcc00).'),
)


class PublishedPostManager(models.Manager):
    def published(self):
        return self.filter(is_visible=True)


class Category(models.Model):
    """
    Top-level taxonomy grouping for posts.

    name_en / name_fa store the bilingual display names.
    slug is used in URLs: /posts/category/<slug>/
    order controls the display sequence in navigation and admin lists.
    """

    name_en = models.CharField(max_length=120)
    name_fa = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True)
    description_en = models.TextField(blank=True)
    description_fa = models.TextField(blank=True)
    # Lower numbers appear first in navigation (e.g. 0 = leftmost tab).
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name_en']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def __str__(self):
        return self.name_en

    def get_absolute_url(self):
        """Return the canonical URL: /posts/category/<slug>/"""
        from django.urls import reverse
        return reverse('posts:category_detail', kwargs={'cat_slug': self.slug})


class Subcategory(models.Model):
    """
    Optional second-level taxonomy scoped under a Category.

    Accessed via /posts/category/<cat_slug>/<sub_slug>/
    slug is unique within a category (not globally), enforced by unique_together.
    """

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='subcategories'
    )
    name_en = models.CharField(max_length=120)
    name_fa = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, allow_unicode=True)

    class Meta:
        # A slug must be unique per category, not globally.
        constraints = [
            models.UniqueConstraint(fields=['category', 'slug'], name='unique_subcategory_slug_per_category')
        ]
        verbose_name = _('Subcategory')
        verbose_name_plural = _('Subcategories')

    def __str__(self):
        return f"{self.category.name_en} / {self.name_en}"

    def get_absolute_url(self):
        """Return the canonical URL: /posts/category/<cat_slug>/<sub_slug>/"""
        from django.urls import reverse
        return reverse('posts:subcategory_detail', kwargs={
            'cat_slug': self.category.slug,
            'sub_slug': self.slug,
        })


class PostType(models.Model):
    """
    Classifies a post's content format (e.g. "Translation", "Original EN", "Original FA").

    accent_color is a hex string (e.g. #ffcc00) rendered as a colour badge
    on post cards and detail pages.
    label() returns the localised name based on the active language.
    """

    name_en = models.CharField(max_length=80)
    name_fa = models.CharField(max_length=80, blank=True)
    slug = models.SlugField(max_length=40, unique=True, allow_unicode=True)
    accent_color = models.CharField(
        max_length=7,
        default='#ffcc00',
        validators=[_hex_color_validator],
        help_text=_('Hex color used for article accents (e.g. #ffcc00)'),
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name_en']
        verbose_name = _('Post type')
        verbose_name_plural = _('Post types')

    def __str__(self):
        return self.name_en

    def label(self, language_code='en'):
        """Return the name in the requested language, falling back to English."""
        if language_code == 'fa' and self.name_fa:
            return self.name_fa
        return self.name_en


class Tag(models.Model):
    """
    Free-form label applied to posts.

    slug is generated from name via slugify() in admin_tags view.
    Posts are filtered by tag via ?tag=<slug> on the post list.
    """

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True, allow_unicode=True)

    class Meta:
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')

    def __str__(self):
        return self.name


class Post(models.Model):
    """
    Primary content model representing an article or news post.

    Key field notes
    ---------------
    slug          – URL-safe unique identifier; used in get_absolute_url().
    category      – PROTECT: deleting a category that has posts is blocked.
    subcategory   – SET_NULL: removing a subcategory doesn't delete its posts.
    post_type     – PROTECT: deleting a type that has posts is blocked.
    publisher     – SET_NULL: deleting a user preserves their posts.
    author_name   – free-text field for display; distinct from the publisher
                    FK so that bylines can differ from the account owner.
    body          – HTML content from the WYSIWYG editor, sanitised by
                    clean_post_body() in posts/utils.py.
    cover_image   – resized to 1200×675 JPEG by posts/image_processing.py.
    cover_alt     – accessibility text for the cover image.
    attachment    – downloadable file (PDF, archive, audio, …) validated in
                    posts/forms.py clean_attachment().
    is_visible    – visibility toggle; False hides the post from all public views.

    Computed properties
    -------------------
    attachment_filename – bare filename (no upload path prefix).
    reading_time        – estimated reading time in minutes at 200 wpm.
    """

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='posts'
    )
    subcategory = models.ForeignKey(
        Subcategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='posts'
    )
    post_type = models.ForeignKey(
        PostType, on_delete=models.PROTECT, related_name='posts'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')

    author_name = models.CharField(
        max_length=200, blank=True,
        help_text=_('First and last name, or team name')
    )
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='published_posts'
    )

    summary = models.TextField(blank=True, help_text=_('Short intro / excerpt'))
    body = models.TextField()
    body_md_file = models.FileField(
        upload_to='posts/md/',
        blank=True,
        null=True,
        verbose_name=_('Markdown File / فایل مارک‌داون'),
    )
    cover_image = models.ImageField(upload_to='posts/covers/', blank=True, null=True)
    cover_alt = models.CharField(
        max_length=255, blank=True,
        help_text=_('Describe the image for screen readers (leave blank if purely decorative)'),
    )
    attachment = models.FileField(upload_to='posts/files/', blank=True, null=True)

    # pub_date defaults to now so new posts appear immediately if visible.
    pub_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reading_time_override = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name=_('Reading Time Override (min)'),
        help_text=_('Override auto-calculated reading time. Leave blank for automatic.'),
    )
    is_visible = models.BooleanField(default=True, verbose_name=_('Show?'))
    view_count = models.PositiveIntegerField(default=0, editable=False, verbose_name=_('Total Views'))
    unique_view_count = models.PositiveIntegerField(default=0, editable=False, verbose_name=_('Unique Views'))

    objects = PublishedPostManager()

    class Meta:
        # Most-recently published posts appear first in querysets.
        ordering = ['-pub_date']
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')
        indexes = [
            models.Index(fields=['-pub_date', 'is_visible'], name='post_pubdate_visible_idx'),
            models.Index(fields=['category', 'is_visible'], name='post_category_visible_idx'),
            models.Index(fields=['post_type', 'is_visible'], name='post_type_visible_idx'),
            models.Index(fields=['title'], name='post_title_idx'),
            models.Index(fields=['author_name'], name='post_author_idx'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Return the canonical URL: /posts/<slug>/"""
        return reverse('posts:post_detail', kwargs={'slug': self.slug})

    def save(self, **kwargs):
        """
        Sanitise ``body`` via ``clean_post_body`` on every save.

        This guarantees the HTML in the database is always sanitised regardless
        of how the Post is created or modified (form, admin, shell, fixtures,
        migrations, seed commands).  The render-time clean in the
        ``render_post_body`` template filter is kept as defense-in-depth.

        ValidationError (e.g. body too long) is re-raised so callers cannot
        accidentally persist unsanitized content.  Unexpected exceptions are
        logged and the body is escaped as plain text to prevent XSS.
        """
        if self.body:
            from .utils import clean_post_body, looks_like_html
            if looks_like_html(self.body):
                from django.core.exceptions import ValidationError
                try:
                    self.body = clean_post_body(self.body)
                except ValidationError:
                    raise  # Let validation errors surface to the caller.
                except Exception:
                    import logging
                    logging.getLogger('posts').exception(
                        'Unexpected error sanitizing post body for post %s',
                        self.pk or '(new)',
                    )
                    from django.utils.html import escape
                    # Store as a plain string (NOT mark_safe) so Django's
                    # template auto-escaping applies on render. The
                    # render_post_body filter detects the escaped entities
                    # and renders them as visible text, not double-escaped.
                    self.body = escape(self.body)
        super().save(**kwargs)

    @property
    def attachment_filename(self):
        """Return just the filename of the attachment, without the upload path."""
        from pathlib import Path
        return Path(self.attachment.name).name if self.attachment else ''

    @property
    def cover_image_url(self):
        """Return cover image URL if file exists, empty string otherwise."""
        try:
            if self.cover_image and self.cover_image.name:
                return self.cover_image.url
        except ValueError:
            pass
        return ''

    @cached_property
    def reading_time(self):
        """
        Estimated reading time in minutes, assuming 200 words per minute.

        If ``reading_time_override`` is set, that value is returned instead.

        HTML tags are stripped before counting so tag markup doesn't inflate
        the word count.  The result is always at least 1 minute.

        cached_property stores the result on the instance so repeated accesses
        within the same request (e.g. listing 12 posts) don't re-strip and
        re-count the HTML each time.
        """
        if self.reading_time_override:
            return self.reading_time_override
        from django.utils.html import strip_tags
        text = strip_tags(self.body) if self.body else ''
        words = len(text.split())
        return max(1, round(words / 200))
