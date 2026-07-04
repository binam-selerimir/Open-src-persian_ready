"""
accounts/forms.py
=================
Django forms for the accounts app:

  LoginForm       – bare username + password form (no ModelForm).
  RegisterForm    – new-user creation with password confirmation and email
                    uniqueness checks; sets is_active=False pending email verify.
  UserEditForm    – edits core user fields + avatar (MIME-validated, EXIF-stripped).
  ProfileEditForm – edits the UserProfile companion record.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from .models import UserProfile
from .models import Certificate, UserCertificate

User = get_user_model()


class LoginForm(forms.Form):
    """
    Simple username + password form.

    Not a ModelForm — we don't want Django to try to bind it to a model
    instance; authentication is handled manually in login_view.
    """
    username = forms.CharField(
        label=_('Username'),
        widget=forms.TextInput(attrs={'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )


class RegisterForm(forms.ModelForm):
    """
    New-account registration form.

    Validation highlights
    ---------------------
    * clean_username  – case-insensitive uniqueness check so 'Alice' and 'alice'
                        cannot both register.
    * clean_email     – required + case-insensitive uniqueness check.
    * clean_password  – runs all AUTH_PASSWORD_VALIDATORS from settings.
    * clean_password2 – confirms the two password fields match.
    * save()          – hashes the password via set_password() and sets
                        is_active=False so the account cannot log in until
                        the email confirmation link is clicked.
    """

    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label=_('Confirm Password'),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        labels = {
            'username': _('Username'),
            'email': _('Email'),
            'first_name': _('First name'),
            'last_name': _('Last name'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email required at the form level for the registration flow.
        self.fields['email'].required = True

    def clean_username(self):
        """Reject the username if another account already uses it (case-insensitive)."""
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_('An account with these details already exists.'))
        return username

    def clean_email(self):
        """Require a non-empty email that hasn't been registered before (case-insensitive)."""
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise forms.ValidationError(_('Email is required.'))
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('An account with these details already exists.'))
        return email

    def clean_password(self):
        """Run all password validators defined in settings.AUTH_PASSWORD_VALIDATORS."""
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password)
        return password

    def clean_password2(self):
        """Confirm the two password entries are identical."""
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError(_('Passwords do not match.'))
        return password2

    def save(self, commit=True):
        """
        Hash the password and disable the account until email is verified.

        is_active=False means authenticate() will return None for this user,
        so they cannot log in until confirm_email_view activates them.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_active = False
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """
    Lets a user edit their own profile fields: names, bilingual bio, avatar, website.

    Avatar handling
    ---------------
    clean_avatar runs three security checks before accepting an upload:
    1. File size limit (max 2 MB) — prevents memory exhaustion in Pillow.
    2. MIME type check via python-magic (reads first 4096 bytes) — prevents
       polyglot files (e.g. a PHP shell disguised as a JPEG).
    3. process_avatar_image pipeline — re-encodes via Pillow to verify integrity,
       strip EXIF metadata (including GPS coordinates), and centre-crop/resize
       to a square AVATAR_SIZE x AVATAR_SIZE image.
    """

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'bio_en', 'bio_fa', 'avatar', 'website']
        labels = {
            'first_name': _('First name'),
            'last_name': _('Last name'),
            'bio_en': _('Bio (English)'),
            'bio_fa': _('Bio (Persian)'),
            'avatar': _('Avatar'),
            'website': _('Website'),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'website': forms.URLInput(attrs={'autocomplete': 'url'}),
        }

    def clean_avatar(self):
        """Validate, MIME-check, and re-encode the uploaded avatar image."""
        avatar = self.cleaned_data.get('avatar')
        if not avatar:
            return avatar

        # --- Size guard -------------------------------------------------------
        max_bytes = 2 * 1024 * 1024  # 2 MB
        if hasattr(avatar, 'size') and avatar.size > max_bytes:
            raise forms.ValidationError(_('Avatar file too large (max 2 MB).'))

        # --- MIME verification ------------------------------------------------
        from posts.utils import detect_mime
        AVATAR_ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
        mime = detect_mime(avatar)
        if mime is None:
            raise forms.ValidationError(_('Could not read file.'))
        if mime not in AVATAR_ALLOWED_MIMES:
            raise forms.ValidationError(
                _('Please upload a valid image file (JPEG, PNG, GIF, or WebP).')
            )

        # --- Pillow re-encode ------------------------------------------------
        # process_avatar_image verifies image integrity, strips EXIF (including
        # GPS data), and normalises to a consistent square format/size suitable
        # for a profile picture (process_cover_image would instead force a wide
        # 16:9 crop meant for post cover banners).
        from posts.image_processing import process_avatar_image
        try:
            return process_avatar_image(avatar)
        except ValueError:
            raise forms.ValidationError(
                _('Please upload a valid image file (JPEG, PNG, GIF, or WebP).')
            )


class ProfileEditForm(forms.ModelForm):
    """
    Lets a user edit their UserProfile fields:
    display name, bilingual headline, skills, and social links.

    Telegram username validation is enforced at the model level via
    RegexValidator — no extra clean method needed here.
    """

    class Meta:
        model = UserProfile
        fields = [
            'display_name', 'headline_en', 'headline_fa',
            'skills', 'linkedin_url', 'github_url', 'telegram',
        ]
        labels = {
            'display_name': _('Display name'),
            'headline_en': _('Headline (English)'),
            'headline_fa': _('Headline (Persian)'),
            'skills': _('Skills'),
            'linkedin_url': _('LinkedIn URL'),
            'github_url': _('GitHub URL'),
            'telegram': _('Telegram'),
        }


class CertificateForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = [
            'name', 'name_fa', 'description', 'description_fa',
            'icon', 'accent_color', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'off'}),
            'name_fa': forms.TextInput(attrs={'dir': 'rtl'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'description_fa': forms.Textarea(attrs={'rows': 3, 'dir': 'rtl'}),
            'accent_color': forms.TextInput(attrs={'type': 'color'}),
        }

    def clean_icon(self):
        icon = self.cleaned_data.get('icon')
        if icon and hasattr(icon, 'size'):
            if icon.size > 2 * 1024 * 1024:
                raise forms.ValidationError(_("Icon must be under 2 MB."))
            import magic
            mime = magic.from_buffer(icon.read(2048), mime=True)
            icon.seek(0)
            if not mime.startswith('image/'):
                raise forms.ValidationError(_("Only image files are allowed for the icon."))
        return icon


class GrantCertificateForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        label=_('User'),
        widget=forms.Select(attrs={'class': 'tom-select'}),
    )
    certificate = forms.ModelChoiceField(
        queryset=Certificate.objects.filter(is_active=True).order_by('name'),
        label=_('Certificate'),
        widget=forms.Select(attrs={'class': 'tom-select'}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': _('Optional note...')}),
    )

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get('user')
        cert = cleaned.get('certificate')
        if user and cert:
            if not cert.is_active:
                raise forms.ValidationError(
                    _("The certificate '%s' is no longer active.") % cert.name
                )
            if UserCertificate.objects.filter(user=user, certificate=cert).exists():
                raise forms.ValidationError(
                    _("%s already has the '%s' certificate.") % (user.username, cert.name)
                )
        return cleaned
