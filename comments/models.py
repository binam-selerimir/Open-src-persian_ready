from django.db import models
from django.utils.translation import gettext_lazy as _


class Comment(models.Model):
    """
    User-submitted comment on a Post.

    Comments require admin approval before appearing publicly.
    author_name and author_email are stored directly (not FK to User)
    to allow guest comments and match the Post.author_name pattern.
    """

    post = models.ForeignKey(
        'posts.Post', on_delete=models.CASCADE, related_name='comments'
    )
    author_name = models.CharField(max_length=150, verbose_name=_('Name'))
    author_email = models.EmailField(verbose_name=_('Email'))
    body = models.TextField(verbose_name=_('Comment'))
    is_approved = models.BooleanField(default=False, verbose_name=_('Approved'))
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        indexes = [
            models.Index(fields=['post', 'is_approved'], name='comment_post_approved_idx'),
            models.Index(fields=['-created_at'], name='comment_created_idx'),
        ]

    def __str__(self):
        return f'{self.author_name} on {self.post.title}'
