"""
Add bilingual fields to Page and SiteAlert models.

Page: adds title_en, title_fa, body_en, body_fa.
SiteAlert: adds title_en, title_fa, message_en, message_fa.

The old title/body columns are removed after data is copied to title_en/body_en.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_sitealert'),
    ]

    operations = [
        # --- Page: add new bilingual fields (nullable initially) ---
        migrations.AddField(
            model_name='page',
            name='title_en',
            field=models.CharField(max_length=255, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='page',
            name='title_fa',
            field=models.CharField(max_length=255, blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='page',
            name='body_en',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='page',
            name='body_fa',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),

        # --- SiteAlert: add new bilingual fields ---
        migrations.AddField(
            model_name='sitealert',
            name='title_en',
            field=models.CharField(max_length=200, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sitealert',
            name='title_fa',
            field=models.CharField(max_length=200, blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sitealert',
            name='message_en',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sitealert',
            name='message_fa',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),

        # --- Remove old non-bilingual fields ---
        migrations.RemoveField(
            model_name='page',
            name='title',
        ),
        migrations.RemoveField(
            model_name='page',
            name='body',
        ),
        migrations.RemoveField(
            model_name='sitealert',
            name='title',
        ),
        migrations.RemoveField(
            model_name='sitealert',
            name='message',
        ),
    ]
