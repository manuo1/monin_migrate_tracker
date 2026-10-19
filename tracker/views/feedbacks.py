from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Min, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import rules, services
from ..choices import FeedbackType
from ..forms import CommentForm, FeedbackForm, FeedbackStaffForm
from ..models import Feedback
from ..statuses import FEEDBACK_STATUS_BY_CODE, FEEDBACK_STATUSES
from ..timeline import build_timeline
from .common import can_add_attachments, distinct_page_and_tab_values, staff_required

# Sortable list columns: URL key -> ORM field.
SORT_FIELDS = {
    "id": "pk",
    "type": "type",
    "page": "page",
    "tab": "tab",
    "article": "article_id",
    "description": "description",
    "author": "author__username",
    "status": "status_rank",
    "date": "created_at",
    "vendor": "vendor_ref",
}


@login_required
def feedback_list(request):
    # Remember the list (filters + sort) for the "back" button of the detail page.
    request.session["feedback_list_url"] = request.get_full_path()

    # Sort statuses by workflow order (statuses.py), not by alphabetical code.
    status_rank = Case(
        *[When(status=s.code, then=Value(i)) for i, s in enumerate(FEEDBACK_STATUSES)],
        default=Value(len(FEEDBACK_STATUSES)),
        output_field=IntegerField(),
    )
    feedbacks = (
        Feedback.objects.select_related("author")
        .prefetch_related("vendor_tickets")
        .annotate(vendor_ref=Min("vendor_tickets__ref"), status_rank=status_rank)
    )

    # Staff sees everything by default; other users see their own feedbacks (and can widen the filter).
    author = request.GET.get("author", "" if request.user.is_staff else "me")
    if author == "me":
        feedbacks = feedbacks.filter(author=request.user)
    elif author.isdigit():
        feedbacks = feedbacks.filter(author_id=author)

    type_ = request.GET.get("type", "")
    if type_:
        feedbacks = feedbacks.filter(type=type_)

    status = request.GET.get("status", "")
    if status in FEEDBACK_STATUS_BY_CODE:
        feedbacks = feedbacks.filter(status=status)

    page = request.GET.get("page", "")
    if page:
        feedbacks = feedbacks.filter(page=page)
    tab = request.GET.get("tab", "")
    if tab:
        feedbacks = feedbacks.filter(tab=tab)
    pages, tabs = distinct_page_and_tab_values(Feedback, page)

    q = request.GET.get("q", "").strip()
    if q:
        feedbacks = feedbacks.filter(
            Q(page__icontains=q) | Q(tab__icontains=q) | Q(article_id__icontains=q) | Q(description__icontains=q)
        )

    sort = request.GET.get("sort", "date")
    if sort not in SORT_FIELDS:
        sort = "date"
    order = "asc" if request.GET.get("order") == "asc" else "desc"
    feedbacks = feedbacks.order_by(("-" if order == "desc" else "") + SORT_FIELDS[sort], "-pk")

    base_query = request.GET.copy()
    base_query.pop("sort", None)
    base_query.pop("order", None)

    return render(
        request,
        "tracker/feedback_list.html",
        {
            "feedbacks": list(feedbacks),
            "statuses": FEEDBACK_STATUSES,
            "types": FeedbackType.choices,
            "filters": {"author": author, "type": type_, "status": status, "q": q, "page": page, "tab": tab},
            "pages": pages,
            "tabs": tabs,
            "authors": get_user_model().objects.filter(feedbacks__isnull=False).distinct().order_by("username"),
            "sort": sort,
            "order": order,
            "base_query": base_query.urlencode(),
        },
    )


def _copy_source(request):
    """Feedback to copy (`copy` parameter): any logged-in user can copy any feedback."""
    pk = request.GET.get("copy") or request.POST.get("copy") or ""
    return Feedback.objects.filter(pk=pk).first() if pk.isdigit() else None


@login_required
def feedback_create(request):
    """New feedback, optionally prefilled from `?copy=<id>` (fields and attachments by reference, no comments)."""
    source = _copy_source(request)
    kept_ids = set(request.POST.getlist("copy_attachment")) if request.method == "POST" else None

    if request.method == "POST":
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            files = data.pop("files")
            feedback = services.create_feedback(
                author=request.user,
                files=files,
                source=source,
                copied_attachment_ids=kept_ids if source else (),
                **data,
            )
            messages.success(request, f"Ticket #{feedback.pk} créé.")
            return redirect("feedback_detail", pk=feedback.pk)
    else:
        feedback_type = request.GET.get("type", "")
        initial = {"type": feedback_type if feedback_type in FeedbackType.values else FeedbackType.BUG}
        if source:
            initial.update(
                type=source.type,
                page=source.page,
                tab=source.tab,
                article_id=source.article_id,
                description=source.description,
            )
            messages.info(
                request,
                f"Copie du ticket #{source.pk} : champs, description et pièces jointes repris "
                "(commentaires et historique non copiés).",
            )
        form = FeedbackForm(initial=initial)

    copied_attachments = [
        {"attachment": a, "checked": kept_ids is None or str(a.pk) in kept_ids}
        for a in (source.attachments.all() if source else [])
    ]
    return render(
        request,
        "tracker/feedback_form.html",
        {
            "form": form,
            "source": source,
            "copied_attachments": copied_attachments,
            "my_feedbacks": Feedback.objects.filter(author=request.user),
        },
    )


@staff_required
def feedback_edit(request, pk):
    """Staff edits type, page, tab and article of a feedback; each changed field is traced. Description is read-only."""
    feedback = get_object_or_404(Feedback, pk=pk)
    if request.method == "POST":
        before = Feedback.objects.get(pk=pk)  # the form mutates `feedback`: keep an untouched copy to diff against
        form = FeedbackStaffForm(request.POST, instance=feedback)
        if form.is_valid():
            changes = services.save_changes(before, form.instance, request.user)
            if changes:
                messages.success(request, f"Ticket #{pk} modifié ({changes} changement(s)).")
            else:
                messages.info(request, "Aucune modification.")
            return redirect("feedback_detail", pk=pk)
    else:
        form = FeedbackStaffForm(instance=feedback)
    return render(request, "tracker/feedback_edit.html", {"form": form, "feedback": feedback})


@login_required
def feedback_detail(request, pk):
    feedback = get_object_or_404(Feedback.objects.select_related("author"), pk=pk)
    return _render_detail(request, feedback)


def _render_detail(request, feedback, retest_comment=""):
    return render(
        request,
        "tracker/feedback_detail.html",
        {
            "feedback": feedback,
            "vendor_tickets": feedback.vendor_tickets.all(),
            "attachments": feedback.attachments.all(),
            "timeline": build_timeline(feedback),
            "comment_form": CommentForm(),
            "retest_open": rules.retest_is_open(feedback, request.user),
            "retest_comment": retest_comment,
            "can_add_attachments": can_add_attachments(request.user, feedback),
            "back_url": request.session.get("feedback_list_url") or reverse("feedback_list"),
        },
    )


@login_required
@require_POST
def retest(request, pk):
    """Rule T2: the author or staff answers a retest request (403 otherwise)."""
    feedback = get_object_or_404(Feedback.objects.select_related("author"), pk=pk)
    comment = request.POST.get("comment", "")
    try:
        status = services.answer_retest(feedback, request.user, request.POST.get("answer"), comment)
    except ValueError as error:
        messages.error(request, str(error))
        return _render_detail(request, feedback, retest_comment=comment)
    messages.success(request, f"Retest enregistré : {FEEDBACK_STATUS_BY_CODE[status].label}.")
    return redirect("feedback_detail", pk=pk)


@login_required
@require_POST
def add_comment(request, pk):
    """Any logged-in user can comment on any feedback."""
    feedback = get_object_or_404(Feedback, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        services.add_comment(feedback, request.user, form.cleaned_data["text"])
    else:
        messages.error(request, "Le commentaire est vide.")
    return redirect("feedback_detail", pk=pk)
