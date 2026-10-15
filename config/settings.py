"""
Django settings for the KararVeremedim project.

Configuration is read from environment variables (a local `.env` file is
loaded automatically). See `.env.example` for the available variables.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------

def env_flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


DEBUG = env_flag("DJANGO_DEBUG")

# "Parolamı unuttum" page: built but off until password reset is implemented
# (it only collects an e-mail address and does not send anything yet).
PASSWORD_RESET_PAGE_ENABLED = env_flag("PASSWORD_RESET_PAGE_ENABLED")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")
    SECRET_KEY = "django-insecure-local-development-key-do-not-use-in-production"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Vercel terminates TLS and forwards the original scheme in this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "polls",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "polls.context_processors.create_poll_url",
                "accounts.context_processors.features",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Database ---------------------------------------------------------------
# DATABASE_URL points to Supabase PostgreSQL. Without it we fall back to SQLite.

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, ssl_require=True)}
    # Supabase transaction pooler (port 6543) does not support persistent
    # connections, server-side cursors or server-side prepared statements.
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --- Auth -------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

# Sign in with e-mail address or username (see accounts/backends.py).
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrUsernameBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/giris/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"


# --- Internationalization ---------------------------------------------------

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# --- Static files -----------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Vercel detects STATIC_ROOT, runs collectstatic during the build and serves
# the result from its CDN.
STATIC_ROOT = BASE_DIR / "staticfiles"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
