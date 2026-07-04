# Hand-written migration — adds two composite indexes to the Post table.
# Equivalent to running: python manage.py makemigrations posts
# after adding indexes to Post.Meta in posts/models.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='post',
            index=models.Index(
                fields=['-pub_date', 'is_visible'],
                name='post_pubdate_visible_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(
                fields=['category', 'is_visible'],
                name='post_category_visible_idx',
            ),
        ),
    ]
