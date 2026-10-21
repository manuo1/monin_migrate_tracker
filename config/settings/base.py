"""Settings shared by every environment. Private values come from environment variables (see .env.example)."""

from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Tests and CI set DJANGO_READ_DOT_ENV_FILE=False so they never depend on a local .env.
if env.bool("DJANGO_READ_DOT_ENV_FILE", default=True):
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "tracker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "tracker.middleware.ContentSecurityPolicyMiddleware",
    "axes.middleware.AxesMiddleware",  # must stay last
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
                "tracker.context_processors.reference_lists",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite in development, PostgreSQL in production (DATABASE_URL=postgres://user:password@host:5432/name).
DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")}

# Login throttling (django-axes): lock an account after too many failed attempts, whatever the IP
# (behind a reverse proxy the IP is unreliable; the cost is that someone can lock a given account for a while).
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # first: refuses locked accounts
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=env.int("AXES_COOLOFF_MINUTES", default=15))
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
# axes.W006 (no 'ip_address' in the lockout parameters) is deliberate: the IP is unreliable behind a reverse proxy.
# Known residual risk: password spraying (one attempt on many accounts) is not slowed down.
SILENCED_SYSTEM_CHECKS = ["axes.W006"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Attachments live outside the repository. Going through STORAGES keeps a later move to S3 a pure configuration change.
_media_root = Path(env("MEDIA_ROOT", default="media"))
MEDIA_ROOT = _media_root if _media_root.is_absolute() else BASE_DIR / _media_root
MEDIA_URL = "media/"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "feedback_list"
LOGOUT_REDIRECT_URL = "login"

# Allows PDF previews in an iframe on the same site.
X_FRAME_OPTIONS = "SAMEORIGIN"

# Vendor Jira: private values, never hardcoded in the (public) repository.
JIRA_BASE_URL = env("JIRA_BASE_URL", default="")
JIRA_CREATE_FORM_URL = env("JIRA_CREATE_FORM_URL", default="")
JIRA_REF_PREFIX = env("JIRA_REF_PREFIX", default="")

# Logging: everything goes to stdout (the process manager / container collects it).
# LOG_FORMAT: "plain" (default, readable in development) or "json" (default in production, see prod.py).
LOG_LEVEL = env.str("LOG_LEVEL", default="INFO").upper()
LOG_FORMAT = env.str("LOG_FORMAT", default="plain")
if LOG_FORMAT not in {"plain", "json"}:
    raise ImproperlyConfigured('LOG_FORMAT must be "plain" or "json".')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        "json": {"()": "tracker.logs.JsonFormatter"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": LOG_FORMAT}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    # Replaces Django's default "django" logger (console only when DEBUG, mail_admins) to avoid duplicates.
    "loggers": {"django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False}},
}
