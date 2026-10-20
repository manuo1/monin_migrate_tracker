from django.utils.functional import SimpleLazyObject

from .models import Page, Tab


def reference_lists(request):
    """Page and tab reference lists (names), available in every template.

    Evaluated on demand: a template that does not use them triggers no query.
    """
    return {
        "ref_pages": SimpleLazyObject(lambda: list(Page.objects.values_list("name", flat=True))),
        "ref_tabs": SimpleLazyObject(lambda: list(Tab.objects.values_list("name", flat=True))),
    }
