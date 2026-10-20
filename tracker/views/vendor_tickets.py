from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .. import services
from ..forms import VendorTicketForm
from ..models import Feedback, VendorTicket
from ..statuses import FEEDBACK_STATUS_BY_CODE, VENDOR_IN_PROGRESS, VENDOR_STATUS_BY_CODE, VENDOR_STATUSES
from .common import distinct_page_and_tab_values, staff_required

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


@login_required
def vendor_ticket_detail(request, pk):
    ticket = get_object_or_404(VendorTicket, pk=pk)
    return render(
        request,
        "tracker/vendor_ticket_detail.html",
        {
            "ticket": ticket,
            "feedbacks": ticket.feedbacks.select_related("author"),
            "events": ticket.events.select_related("author").order_by("-date", "-pk"),
            "back_url": request.session.get("vendor_ticket_list_url") or reverse("vendor_ticket_list"),
        },
    )


@staff_required
def vendor_ticket_create(request):
    """
    Staff creates a vendor ticket. With `?feedback=<id>`: form prefilled from that feedback (page, tab, Jira-format
    description, status "in progress", today's date), Jira reference mandatory, and the new ticket is linked to it.
    """
    pk = request.GET.get("feedback", "")
    source = Feedback.objects.filter(pk=pk).first() if pk.isdigit() else None
    initial = {"ref": settings.JIRA_REF_PREFIX}
    if source:
        initial.update(
            page=source.page,
            tab=source.tab,
            title=f"{source.page} {source.tab}".strip(),
            description=services.build_vendor_description(source),
            status=VENDOR_IN_PROGRESS,
            created_on=timezone.localdate(),
        )
    form = VendorTicketForm(request.POST or None, initial=initial, ref_required=source is not None)
    if request.method == "POST" and form.is_valid():
        status_before = source.status if source else None
        ticket = services.create_vendor_ticket(author=request.user, source=source, **form.cleaned_data)
        message = "Ticket Aptean créé."
        if source:
            message = f"Ticket Aptean créé et lié au ticket Monin #{source.pk}."
            if source.status != status_before:  # rule T1 moved the status when the vendor ticket was linked
                message += f" Le ticket Monin passe en « {FEEDBACK_STATUS_BY_CODE[source.status].label} »."
        messages.success(request, message)
        return redirect("vendor_ticket_detail", pk=ticket.pk)
    return render(
        request,
        "tracker/vendor_ticket_create.html",
        {"form": form, "source": source, "jira_form_url": settings.JIRA_CREATE_FORM_URL},
    )


@staff_required
def vendor_ticket_edit(request, pk):
    """Staff edits a vendor ticket; each changed field is traced."""
    ticket = get_object_or_404(VendorTicket, pk=pk)
    if request.method == "POST":
        before = VendorTicket.objects.get(pk=pk)  # the form mutates `ticket`: keep an untouched copy to diff against
        form = VendorTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            changes = services.save_vendor_ticket(before, form.instance, request.user)
            if changes:
                messages.success(request, f"Ticket Aptean modifié ({changes} changement(s)).")
            else:
                messages.info(request, "Aucune modification.")
            return redirect("vendor_ticket_detail", pk=pk)
    else:
        form = VendorTicketForm(instance=ticket)
    return render(request, "tracker/vendor_ticket_edit.html", {"form": form, "ticket": ticket})
