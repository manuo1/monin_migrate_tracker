"""Project middlewares: language selection (switch cookie only) and Content-Security-Policy header.

Django 5.2 has no built-in CSP.
"""

import contextlib

from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class CookieLocaleMiddleware(LocaleMiddleware):
    """Language = the switch cookie, else LANGUAGE_CODE. The browser's Accept-Language is deliberately ignored."""

    def process_request(self, request):
        language = settings.LANGUAGE_CODE
        cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie:
            with contextlib.suppress(LookupError):
                language = translation.get_supported_language_variant(cookie)
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()


# Strict on scripts (no inline JS, no CDN: everything is served from `static/`). Inline styles are still allowed:
# templates use `style=` attributes. `blob:` in img-src is for the local thumbnails of the attachment dropzone.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
    ]
)

# The Django admin ships its own inline scripts: it keeps the default behaviour.
EXCLUDED_PREFIXES = ("/admin/",)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(EXCLUDED_PREFIXES) and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response
