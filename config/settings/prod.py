from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set in production.")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Deliberately silenced (see handoff):
# - W019: X_FRAME_OPTIONS stays SAMEORIGIN because attachment PDFs are previewed in an iframe of the same site.
# - W021: HSTS preload is a long-term public commitment, not wanted for an internal tool.
SILENCED_SYSTEM_CHECKS = [*SILENCED_SYSTEM_CHECKS, "security.W019", "security.W021"]

# Set BEHIND_PROXY=True only when a trusted reverse proxy terminates TLS and sets X-Forwarded-Proto.
if env.bool("BEHIND_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Static files are served by the app itself (WhiteNoise) so the container needs no web server for them.
# Attachments are NOT static: they go through the authenticated download view.
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]

# Structured logs (one JSON object per line) unless LOG_FORMAT says otherwise.
LOGGING["handlers"]["console"]["formatter"] = env.str("LOG_FORMAT", default="json")
