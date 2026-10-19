from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.shortcuts import render

from ..models import VendorTicket
from ..statuses import VENDOR_STATUS_BY_CODE, VENDOR_STATUSES
from .common import distinct_page_and_tab_values

# Sortable list columns: URL key -> ORM field.
SORT_FIELDS = {
    "ref": "ref",
    "title": "title",
    "description": "description",
    "page": "page",
    "tab": "tab",
    "status": "status_rank",
    "date": "created_on",
    "feedbacks": "feedback_count",
}


def filtered_vendor_tickets(request):
    """Vendor tickets filtered and sorted from the query string, with the context of the filter bar."""
    # Sort statuses by workflow order (statuses.py), not by alphabetical code; no status comes last.
    status_rank = Case(
        *[When(status=s.code, then=Value(i)) for i, s in enumerate(VENDOR_STATUSES)],
        default=Value(len(VENDOR_STATUSES)),
        output_field=IntegerField(),
    )
    tickets = VendorTicket.objects.prefetch_related("feedbacks").annotate(
        status_rank=status_rank, feedback_count=Count("feedbacks")
    )

    status = request.GET.get("status", "")
    if status == "none":
        tickets = tickets.filter(status="")
    elif status in VENDOR_STATUS_BY_CODE:
        tickets = tickets.filter(status=status)

    linked = request.GET.get("linked", "")
    if linked == "no":
        tickets = tickets.filter(feedback_count=0)
    elif linked == "yes":
        tickets = tickets.filter(feedback_count__gt=0)

    page = request.GET.get("page", "")
    if page:
        tickets = tickets.filter(page=page)
    tab = request.GET.get("tab", "")
    if tab:
        tickets = tickets.filter(tab=tab)
    pages, tabs = distinct_page_and_tab_values(VendorTicket, page)

    q = request.GET.get("q", "").strip()
    if q:
        tickets = tickets.filter(
            Q(ref__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(page__icontains=q)
            | Q(tab__icontains=q)
        )

    sort = request.GET.get("sort", "date")
    if sort not in SORT_FIELDS:
        sort = "date"
    order = "asc" if request.GET.get("order") == "asc" else "desc"
    field = F(SORT_FIELDS[sort])
    # NULLs last in both directions, whatever the database (SQLite and PostgreSQL differ by default).
    tickets = tickets.order_by(field.desc(nulls_last=True) if order == "desc" else field.asc(nulls_last=True), "-pk")

    base_query = request.GET.copy()
    base_query.pop("sort", None)
    base_query.pop("order", None)

    return {
        "tickets": list(tickets),
        "statuses": VENDOR_STATUSES,
        "filters": {"status": status, "linked": linked, "q": q, "page": page, "tab": tab},
        "pages": pages,
        "tabs": tabs,
        "sort": sort,
        "order": order,
        "base_query": base_query.urlencode(),
    }


@login_required
def vendor_ticket_list(request):
    # Remember the list (filters + sort) for the "back" button of the vendor ticket pages.
    request.session["vendor_ticket_list_url"] = request.get_full_path()
    return render(request, "tracker/vendor_ticket_list.html", filtered_vendor_tickets(request))
