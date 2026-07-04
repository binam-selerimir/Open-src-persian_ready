from django import forms
from django.utils.translation import gettext_lazy as _

from .image_processing import process_cover_image
from .models import Post, PostType, Subcategory, Tag
from .utils import clean_post_body, looks_like_html

ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.pdf', '.epub', '.zip', '.tar', '.gz',
    '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
    '.odt', '.ods', '.odp',
    '.txt', '.md', '.csv',
    '.mp3', '.ogg', '.wav', '.m4a', '.flac',
    '.mp4', '.webm',
}

MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024  # 100 MB

ATTACHMENT_ALLOWED_MIMES = {
    'application/pdf',
    'application/epub+zip',
    'application/zip',
    'application/gzip',
    'application/x-tar',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.oasis.opendocument.text',
    'application/vnd.oasis.opendocument.spreadsheet',
    'application/vnd.oasis.opendocument.presentation',
    'text/plain',
    'text/csv',
    'audio/mpeg',
    'audio/ogg',
    'audio/wav',
    'audio/x-m4a',
    'audio/flac',
    'video/mp4',
    'video/webm',
}


class PostForm(forms.ModelForm):
    body_mode = forms.ChoiceField(
        choices=[('write', 'Write'), ('upload_md', 'Upload Markdown')],
        initial='write',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'body_mode'}),
    )

    class Meta:
        model = Post
        fields = [
            'title', 'slug', 'category', 'subcategory', 'post_type',
            'tags', 'author_name', 'summary', 'body', 'body_md_file',
            'cover_image', 'cover_alt', 'attachment', 'reading_time_override',
            'pub_date', 'is_visible',
        ]
        labels = {
            'title': _('Title'),
            'slug': _('Slug'),
            'category': _('Category'),
            'subcategory': _('Subcategory'),
            'post_type': _('Post Type'),
            'tags': _('Tags'),
            'author_name': _('Author Name'),
            'summary': _('Summary'),
            'body': _('Body'),
            'body_md_file': _('Markdown File / فایل مارک‌داون'),
            'cover_image': _('Cover Image'),
            'cover_alt': _('Cover Alt Text'),
            'attachment': _('Attachment'),
            'reading_time_override': _('Reading Time Override (min)'),
            'pub_date': _('Publish Date'),
            'is_visible': _('Show?'),
        }
        widgets = {
            'body': forms.Textarea(attrs={
                'rows': 20,
                'class': 'richtext-source',
                'id': 'id_body',
            }),
            'body_md_file': forms.FileInput(attrs={'accept': '.md,text/markdown,text/plain'}),
            'summary': forms.Textarea(attrs={'rows': 4}),
            'pub_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'cover_image': forms.FileInput(attrs={
                'class': 'sr-only cover-file-input',
                'id': 'id_cover_image',
                'accept': 'image/jpeg,image/png,image/gif,image/webp',
            }),
            'tags': forms.SelectMultiple(attrs={
                'class': 'tag-select-search',
                'id': 'id_tags',
                'data-placeholder': _('Search and select tags…'),
                'data-no-tags-text': _('No tags found'),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.body_md_file:
            self.fields['body_mode'].initial = 'upload_md'
        self.fields['category'].required = True
        # body is not always required — in upload_md mode it may be empty.
        # The clean() method enforces the requirement based on the selected mode.
        self.fields['body'].required = False
        self.fields['post_type'].queryset = PostType.objects.all()
        self.fields['tags'].queryset = Tag.objects.all().order_by('name')
        self.fields['tags'].help_text = _('Type to search when you have many tags.')
        self.fields['subcategory'].queryset = Subcategory.objects.none()
        self.fields['subcategory'].widget.attrs.update({
            'data-loading-text': _('Loading…'),
            'data-error-text': _('Error loading subcategories'),
        })

        # Set default post type for new posts
        if not self.instance.pk and not self.data:
            default_type = (
                PostType.objects.filter(slug='original_en').first()
                or PostType.objects.first()
            )
            if default_type:
                self.fields['post_type'].initial = default_type.pk

        # Populate subcategory queryset based on selected/existing category
        if 'category' in self.data:
            try:
                cat_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = Subcategory.objects.filter(
                    category_id=cat_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.category_id:
            self.fields['subcategory'].queryset = (
                self.instance.category.subcategories.all()
            )

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if not attachment:
            return attachment
        from pathlib import Path
        ext = Path(attachment.name).suffix.lower()
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise forms.ValidationError(
                _('File type "%(ext)s" is not allowed. Permitted types: %(types)s') % {
                    'ext': ext,
                    'types': ', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS)),
                }
            )
        if attachment.size > MAX_ATTACHMENT_BYTES:
            max_mb = MAX_ATTACHMENT_BYTES // (1024 * 1024)
            raise forms.ValidationError(
                _('Attachment too large (max %(max_mb)s MB).') % {'max_mb': max_mb}
            )
        # MIME verification via shared utility (local import to avoid circular dependency).
        from .utils import detect_mime
        mime = detect_mime(attachment)
        if mime is None:
            raise forms.ValidationError(_('Could not determine file type.'))
        if mime not in ATTACHMENT_ALLOWED_MIMES:
            raise forms.ValidationError(
                _('Invalid file content (detected type: %(mime)s). '
                  'Please upload a file matching its extension.') % {'mime': mime}
            )
        return attachment

    def clean_cover_image(self):
        cover = self.cleaned_data.get('cover_image')
        if not cover:
            return cover
        try:
            return process_cover_image(cover)
        except ValueError:
            raise forms.ValidationError(
                _('Please upload a valid image file (JPEG, PNG, GIF, or WebP).')
            )

    def clean_body(self):
        body = self.cleaned_data.get('body', '')
        if looks_like_html(body):
            return clean_post_body(body)
        # Local import to avoid circular dependency between posts and utils
        from .utils import MAX_POST_BODY_LENGTH
        if len(body) > MAX_POST_BODY_LENGTH:
            raise forms.ValidationError(
                _('Body is too long (%(length)s characters). Maximum is %(max)s.')
                % {'length': len(body), 'max': MAX_POST_BODY_LENGTH}
            )
        return body

    def clean_body_md_file(self):
        f = self.cleaned_data.get('body_md_file')
        if not f:
            return f
        name = getattr(f, 'name', '')
        if not name.lower().endswith('.md'):
            raise forms.ValidationError(
                _('Only .md files are allowed. / فقط فایل‌های .md مجاز هستند.')
            )
        if f.size > 1 * 1024 * 1024:
            raise forms.ValidationError(
                _('Markdown file must be under 1 MB. / فایل مارک‌داون باید کمتر از ۱ مگابایت باشد.')
            )
        return f

    def clean(self):
        cleaned_data = super().clean()
        body = cleaned_data.get('body', '').strip() if cleaned_data.get('body') else ''
        md_file = cleaned_data.get('body_md_file')
        mode = cleaned_data.get('body_mode', 'write')

        existing_md = bool(
            self.instance and self.instance.pk and self.instance.body_md_file
        )

        # An attacker could manipulate the hidden body_mode field to submit
        # an empty body while forcing write mode. By re-deriving mode from
        # the actual file presence (defense-in-depth), we prevent this.
        if md_file or existing_md:
            mode = 'upload_md'

        if mode == 'upload_md':
            if not md_file and not existing_md:
                self.add_error(
                    'body_md_file',
                    _('Please upload a .md file. / لطفاً یک فایل .md آپلود کنید.')
                )
        else:
            if not body:
                self.add_error(
                    'body',
                    _('Post body is required. / متن نوشته الزامی است.')
                )

        return cleaned_data
