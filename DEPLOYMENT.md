# Deployment Guide — cPanel Shared Hosting

Complete guide to deploy **OpenSrcPersian** on cPanel shared hosting with real email sending.

---

## 1. cPanel Setup (Server-Side)

### Create Python App

1. Go to **cPanel → Software → Setup Python App** (or "Python Selector")
2. Select **Python 3.12** (required by Django 6.0)
3. Click **Create Application**
4. Set:
   - **Application root**: `myproject` (your project folder)
   - **Application URL**: `/` (root) or subdirectory
   - **Application startup file**: `passenger_wsgi.py`
   - **Application entry point**: `application`

### Create `passenger_wsgi.py`

Create this file in your project root (same level as `manage.py`):

```python
import os
from myproject.wsgi import application
```

### Upload Project

Upload all project files via **File Manager** or **SSH/Git**. Make sure:

- `manage.py`, `myproject/`, all apps are at the application root
- `passenger_wsgi.py` is at the root
- `.env` is inside the `myproject/` folder (next to `settings.py`)

### Create MySQL Database

1. Go to **cPanel → MySQL Databases**
2. Create a database (e.g., `opensrcp_db`)
3. Create a user with a strong password
4. Add the user to the database with **All Privileges**
5. Note the credentials: `username`, `password`, `dbname`, `localhost`

---

## 2. Environment Variables (`.env`)

Replace your current `.env` with production values:

```env
# ── Security ──
SECRET_KEY=your-new-secret-key-here
DEBUG=False
ALLOWED_HOSTS=opensrcpersian.org,www.opensrcpersian.org

# ── Database (MySQL from cPanel) ──
DATABASE_URL=mysql://dbuser:dbpassword@localhost:3306/dbname

# ── CSRF ──
CSRF_TRUSTED_ORIGINS=https://opensrcpersian.org,https://www.opensrcpersian.org

# ── Email (cPanel SMTP) ──
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.opensrcpersian.org
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@opensrcpersian.org
EMAIL_HOST_PASSWORD=your-email-password-here
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@opensrcpersian.org
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 3. Email Setup on cPanel

### Create an Email Account

1. Go to **cPanel → Email → Email Accounts**
2. Click **Create**
3. Set:
   - **Domain**: `opensrcpersian.org`
   - **Username**: `noreply` (or `info`, `admin`, etc.)
   - **Password**: strong password
4. Click **Create**

### Find Your SMTP Settings

Go to **cPanel → Email Accounts → click your account → "Connect Devices"** or **"Configuration Settings"**.

Typical cPanel SMTP values:

| Setting          | Value                              |
|------------------|------------------------------------|
| SMTP Host        | `mail.opensrcpersian.org`          |
| SMTP Port        | `587` (TLS) or `465` (SSL)        |
| Username         | `noreply@opensrcpersian.org`       |
| Password         | the password you set               |
| Encryption       | TLS (587) or SSL (465)             |

### Multiple Email Accounts (Optional)

Create separate accounts for different purposes:

| Email                              | Purpose                            |
|------------------------------------|------------------------------------|
| `noreply@opensrcpersian.org`       | Transactional (confirm, reset)     |
| `info@opensrcpersian.org`          | General contact                    |
| `admin@opensrcpersian.org`         | Admin notifications                |

---

## 4. DNS Records (Critical for Email Deliverability)

In your **domain registrar** or **cPanel Zone Editor**, ensure these records exist:

```dns
# A Record (website)
opensrcpersian.org.        A       YOUR_SERVER_IP

# MX Record (email routing)
opensrcpersian.org.        MX      mail.opensrcpersian.org.  10

# SPF Record (prevents spam spoofing)
opensrcpersian.org.        TXT     "v=spf1 a mx ip4:YOUR_SERVER_IP ~all"

# DMARC (optional but recommended)
_dmarc.opensrcpersian.org. TXT     "v=DMARC1; p=quarantine; rua=mailto:admin@opensrcpersian.org"
```

> **Get your server IP**: cPanel → General Information → "Shared IP Address" or "Dedicated IP"

---

## 5. Post-Deployment Commands (SSH or cPanel Terminal)

```bash
# Navigate to project root
cd ~/myproject

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Seed demo data (optional)
python manage.py seed_pages
python manage.py seed_posts

# Compile translations
python manage.py compilemessages
```

---

## 6. SSL Certificate (HTTPS)

1. Go to **cPanel → Security → SSL/TLS Status** (or "Let's Encrypt")
2. Select `opensrcpersian.org` and `www.opensrcpersian.org`
3. Click **Issue** (auto-provisions Let's Encrypt)
4. Enable **Force HTTPS Redirect** in cPanel → Domains

> Required because `DEBUG=False` forces HTTPS (`SECURE_SSL_REDIRECT=True`).

---

## 7. Verify Email Works

After deployment, test from Django shell:

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    'Test from OpenSrcPersian',
    'Email is working!',
    'noreply@opensrcpersian.org',
    ['your-personal-email@gmail.com'],
    fail_silently=False,
)
```

If it returns `1`, email is working. Check your inbox (and spam folder).

---

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| 500 Error | Check `DEBUG=True` temporarily, or view error logs in cPanel → Metrics → Errors |
| Static files not loading | Run `python manage.py collectstatic --noinput` via SSH |
| Email not sending | Verify SMTP host/port in cPanel → Email Accounts → Connect Devices |
| Email goes to spam | Add SPF/DKIM DNS records, check blacklists at mxtoolbox.com |
| CSRF errors | Ensure `CSRF_TRUSTED_ORIGINS` includes your domain with `https://` |
| Database connection | Verify `DATABASE_URL` format: `mysql://user:pass@localhost:3306/dbname` |
| Migrations not applied | Run `python manage.py migrate` via SSH |
| Permission errors | Set `chmod 755` on project dirs, `chmod 644` on files via File Manager |

---

## Checklist

| Step | Done |
|------|------|
| cPanel Python App created (Python 3.12) | ☐ |
| `passenger_wsgi.py` created | ☐ |
| Project files uploaded | ☐ |
| `.env` updated with `DEBUG=False` | ☐ |
| MySQL database created + credentials in `.env` | ☐ |
| Email account created in cPanel | ☐ |
| `.env` email settings updated with real SMTP | ☐ |
| DNS MX/SPF/DKIM records set | ☐ |
| SSL certificate issued (Let's Encrypt) | ☐ |
| SSH: `pip install -r requirements.txt` | ☐ |
| SSH: `python manage.py migrate` | ☐ |
| SSH: `python manage.py collectstatic --noinput` | ☐ |
| Test email via Django shell | ☐ |
