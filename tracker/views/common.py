from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """Login required, then staff only (403 for a logged-in non-staff user)."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def distinct_page_and_tab_values(model, page=""):
    """Distinct page and tab values of `model` for list filters; tabs are limited to the selected page."""
    pages = model.objects.exclude(page="").values_list("page", flat=True)
    tabs = model.objects.exclude(tab="")
    if page:
        tabs = tabs.filter(page=page)
    return sorted(set(pages), key=str.lower), sorted(set(tabs.values_list("tab", flat=True)), key=str.lower)
