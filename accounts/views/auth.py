from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password as _check_password, make_password as _make_password
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _

from ..email_verification import send_confirmation_email, verify_url_token
from ..forms import LoginForm, RegisterForm
from ..utils import audit, check_rate_limit

User = get_user_model()
_DUMMY_HASH = _make_password("_login_timing_guard_do_not_use_")


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:panel')

    raw_next = request.GET.get('next', '').strip()
    safe_next = raw_next if url_has_allowed_host_and_scheme(
        url=raw_next, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ) else ''

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        # Timing equalization: always run bcrypt against dummy hash first so
        # all failed-login paths take identical CPU time regardless of whether
        # the username exists. This prevents username enumeration via timing.
        _check_password(password, _DUMMY_HASH)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Flush the session to prevent session fixation attacks.
            # Django's login() rotates the session key, but flushing first
            # ensures any pre-login session data is discarded.
            request.session.flush()
            login(request, user)
            audit(request, "LOGIN", "User logged in")
            if user.is_staff:
                audit(request, "ADMIN_LOGIN", "Administrator logged in")
            next_url = request.POST.get('next', '').strip()
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('accounts:panel')

        candidate = User.objects.filter(username=username).first()
        _check_password(password, _DUMMY_HASH)
        if candidate is not None and not candidate.is_active:
            password_matches = candidate.check_password(password)
        else:
            password_matches = False

        if candidate is not None and not candidate.is_active and password_matches:
            audit(request, "LOGIN_FAILED", "Correct credentials for inactive account")
            messages.error(request, _(
                'Please confirm your email address before logging in. '
                'Check your inbox for the confirmation link.'
            ))
            return render(request, 'accounts/login.html', {
                'form': form, 'safe_next': safe_next, 'show_resend': True, 'username': username,
            })

        messages.error(request, _('Invalid username or password.'))
        audit(request, "LOGIN_FAILED", "Failed login attempt")

    return render(request, 'accounts/login.html', {'form': form, 'safe_next': safe_next})


def logout_view(request):
    if request.method == 'POST':
        if request.user.is_authenticated:
            audit(request, "LOGOUT", "User logged out")
        logout(request)
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:panel')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if not check_rate_limit(request, 'register', limit=5):
            messages.error(request, _(
                'Too many registration attempts from your IP. Please try again in an hour.'
            ))
            return render(request, 'accounts/register.html', {'form': form})
        if form.is_valid():
            try:
                from django.db import transaction
                from django.db import IntegrityError
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                form.add_error(None, _('An account with these details already exists.'))
                return render(request, 'accounts/register.html', {'form': form})
            try:
                send_confirmation_email(request, user)
            except Exception:
                user.delete()
                messages.error(request, _(
                    'We could not send the confirmation email. Please try again later.'
                ))
                return render(request, 'accounts/register.html', {'form': form})

            messages.success(request, _(
                'Account created. Please check your email and click the '
                'confirmation link to activate your account.'
            ))
            return redirect('accounts:confirm_email_sent')

    return render(request, 'accounts/register.html', {'form': form})


def confirm_email_sent(request):
    return render(request, 'accounts/confirm_email_sent.html')


def resend_confirmation_email(request):
    if request.method != 'POST':
        return redirect('accounts:login')

    if not check_rate_limit(request, 'resend_confirm', limit=3):
        messages.error(request, _('Too many requests. Please try again in an hour.'))
        return redirect('accounts:login')

    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()

    if username and email:
        try:
            user = User.objects.get(username=username, email=email, is_active=False)
            send_confirmation_email(request, user)
            audit(request, "CONFIRM_EMAIL_RESENT", f"Confirmation email resent for user")
        except User.DoesNotExist:
            audit(request, "CONFIRM_EMAIL_RESENT_FAILED", "Resend requested for non-existent user")
        except Exception:
            pass

    messages.success(request, _(
        'If an account with those details exists and is unconfirmed, '
        'a new confirmation email has been sent.'
    ))
    return redirect('accounts:confirm_email_sent')


def confirm_email_view(request, token):
    if not check_rate_limit(request, 'email_confirm', limit=10, increment=False):
        messages.error(request, _(
            'Too many confirmation attempts from your IP address. '
            'Please try again in an hour.'
        ))
        return redirect('accounts:login')

    user_id = verify_url_token(token)
    if user_id is None:
        check_rate_limit(request, 'email_confirm', limit=10)
        messages.error(request, _('This confirmation link is invalid or has expired.'))
        return redirect('accounts:login')

    from django.shortcuts import get_object_or_404
    user = get_object_or_404(User, pk=user_id)
    if user.is_active:
        messages.info(request, _('Your account is already confirmed. You can log in.'))
        return redirect('accounts:login')

    user.is_active = True
    user.save(update_fields=['is_active'])
    audit(request, "EMAIL_VERIFIED", f"Email address verified for user '{user.username}'")
    messages.success(request, _('Your email has been confirmed. You can now log in.'))
    return redirect('accounts:login')
