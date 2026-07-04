import bleach
from django import forms
from django.utils.translation import gettext_lazy as _

ALLOWED_COMMENT_TAGS = ['p', 'br', 'strong', 'em', 'a']
MAX_COMMENT_LENGTH = 2000


class CommentForm(forms.Form):
    """
    Form for submitting comments on posts.

    Only the body field is exposed. author_name and author_email are set
    from the logged-in user's account in the view — users cannot change
    them when posting a comment.

    Comment body is sanitized with bleach to allow only safe inline tags.
    """

    body = forms.CharField(
        max_length=MAX_COMMENT_LENGTH,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': _('Write your comment…'),
        }),
    )

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError(_('Comment cannot be empty.'))
        return bleach.clean(
            body,
            tags=ALLOWED_COMMENT_TAGS,
            protocols=['http', 'https', 'mailto'],
            strip=True,
        )
