import bleach
from django import forms
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .models import Board, FORUM_SANITIZE_ATTRIBUTES, FORUM_SANITIZE_TAGS


def _sanitize_forum_body(raw_body):
    """Strip + validate + bleach-clean a forum body field (shared by NewThreadForm and ReplyForm)."""
    body = raw_body.strip()
    if len(body) < 10:
        raise forms.ValidationError(_('Body must be at least 10 characters long.'))
    return bleach.clean(
        body,
        tags=FORUM_SANITIZE_TAGS,
        attributes=FORUM_SANITIZE_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        strip=True,
    )


class NewBoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['name_en', 'name_fa', 'description_en', 'description_fa', 'order']
        widgets = {
            'name_en': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Board name (English)'}),
            'name_fa': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Board name (Persian)'}),
            'description_en': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Description (English)'}),
            'description_fa': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Description (Persian)'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'style': 'width:80px'}),
        }

    def clean_name_en(self):
        name = self.cleaned_data.get('name_en', '').strip()
        if not name:
            raise forms.ValidationError(_('Name is required.'))
        return name

    def save(self, commit=True):
        board = super().save(commit=False)
        base_slug = slugify(board.name_en, allow_unicode=True)
        if not base_slug:
            base_slug = 'board'
        slug = base_slug
        counter = 1
        while Board.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        board.slug = slug
        if commit:
            board.save()
        return board


class NewThreadForm(forms.Form):
    title = forms.CharField(
        label=_('Title'),
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': _('Thread title'),
        }),
    )
    body = forms.CharField(
        label=_('Body'),
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 12,
            'placeholder': _('Write your post here…'),
        }),
    )

    def clean_body(self):
        return _sanitize_forum_body(self.cleaned_data.get('body', ''))


class ReplyForm(forms.Form):
    body = forms.CharField(
        label=_('Body'),
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 8,
            'placeholder': _('Write your reply…'),
        }),
    )

    def clean_body(self):
        return _sanitize_forum_body(self.cleaned_data.get('body', ''))
