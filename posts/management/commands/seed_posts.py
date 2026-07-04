"""
posts/management/commands/seed_posts.py
=========================================
Django management command: populate the database with sample content.

Usage:
    python manage.py seed_posts

Creates:
  * 3 post types: Translation, Original (EN), Original (FA) -- created
    automatically via get_or_create if they don't already exist (slugs
    'translation', 'original_en', 'original_fa'). If you already created
    your own PostType rows with these slugs (e.g. via the admin), this
    command reuses them as-is and won't overwrite your names/colors.
  * 3 categories: General, Technology, Culture (with bilingual names).
  * 2 subcategories per category (6 total).
  * 10 tags (Tag 1–10).
  * 15 sample posts (5 per category), each assigned a post type and 3 tags.

All operations use get_or_create or existence checks so the command is
idempotent — duplicate slugs are skipped rather than raising errors.
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from posts.models import Category, Subcategory, Tag, Post, PostType


class Command(BaseCommand):
    help = 'Seed sample post types, categories, subcategories, tags, and posts'

    def handle(self, *args, **options):

        # ── Categories (with bilingual names and slugs) ──────────────────────
        categories_data = [
            ('General',    'عمومی',  'general'),
            ('Technology', 'فناوری', 'technology'),
            ('Culture',    'فرهنگ',  'culture'),
        ]

        # ── Subcategories per category ───────────────────────────────────────
        sub_data = {
            'general':    [('Announcements', 'اطلاعیه‌ها'), ('Updates', 'به‌روزرسانی‌ها')],
            'technology': [('Software',      'نرم‌افزار'),  ('Hardware', 'سخت‌افزار')],
            'culture':    [('Community',     'جامعه'),      ('Education', 'آموزش')],
        }

        # ── Post types — created automatically if missing ───────────────────
        # Previously this command required these three rows to already exist
        # (via PostType.objects.get(), which raised PostType.DoesNotExist on
        # a fresh database). get_or_create makes the command fully
        # self-contained: no admin setup needed before running seed_posts.
        post_types_data = [
            ('translation', 'Translation', 'ترجمه', '#3b82f6'),
            ('original_en', 'Original (EN)', 'نگارش اصلی (انگلیسی)', '#22c55e'),
            ('original_fa', 'Original (FA)', 'نگارش اصلی (فارسی)', '#f97316'),
        ]
        post_types = []
        for i, (slug, name_en, name_fa, accent_color) in enumerate(post_types_data):
            pt, _ = PostType.objects.get_or_create(
                slug=slug,
                defaults={
                    'name_en': name_en,
                    'name_fa': name_fa,
                    'accent_color': accent_color,
                    'order': i,
                },
            )
            post_types.append(pt)

        # ── Create categories and their subcategories ────────────────────────
        categories = {}
        for name_en, name_fa, slug in categories_data:
            cat, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={'name_en': name_en, 'name_fa': name_fa, 'order': len(categories)},
            )
            categories[slug] = cat
            # Create each subcategory within this category.
            for sub_en, sub_fa in sub_data[slug]:
                Subcategory.objects.get_or_create(
                    category=cat,
                    slug=slugify(sub_en, allow_unicode=True),
                    defaults={'name_en': sub_en, 'name_fa': sub_fa},
                )

        # ── Create sample tags ───────────────────────────────────────────────
        tags = []
        for i in range(1, 11):
            tag, _ = Tag.objects.get_or_create(
                slug=f'tag-{i}',
                defaults={'name': f'Tag {i}'},
            )
            tags.append(tag)

        # ── Create 5 sample posts per category ───────────────────────────────
        created_posts = 0
        for slug, cat in categories.items():
            subs = list(cat.subcategories.all())
            for i in range(5):
                title = f'{cat.name_en} Sample Post {i + 1}'
                post_slug = slugify(title, allow_unicode=True)
                # Skip if a post with this slug already exists (idempotency).
                if Post.objects.filter(slug=post_slug).exists():
                    continue
                post = Post.objects.create(
                    title=title,
                    slug=post_slug,
                    category=cat,
                    # Cycle subcategories so each post gets a different one.
                    subcategory=subs[i % len(subs)] if subs else None,
                    # Cycle post types: translation, original_en, original_fa, …
                    post_type=post_types[i % len(post_types)],
                    author_name='Editorial Team',
                    summary=f'A sample post about {cat.name_en.lower()}.',
                    body=(
                        f'This is the body of {title}. It discusses topics related '
                        f'to free software and open technology.'
                    ),
                    pub_date=timezone.now(),
                    is_visible=True,
                )
                # Assign the first three tags to every sample post.
                post.tags.set(tags[:3])
                created_posts += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(post_types)} post types, {len(categories)} categories, '
            f'{Tag.objects.count()} tags, {created_posts} posts.'
        ))