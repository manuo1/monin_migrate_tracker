"""Content-Security-Policy header for the application pages (Django 5.2 has no built-in CSP)."""

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
