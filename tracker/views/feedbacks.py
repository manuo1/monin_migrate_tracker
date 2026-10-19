from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Min, Q, Value, When
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ..choices import FeedbackType
from ..models import Feedback
from ..statuses import FEEDBACK_STATUS_BY_CODE, FEEDBACK_STATUSES
from ..timeline import build_timeline
from .common import distinct_page_and_tab_values

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


@login_required
def feedback_detail(request, pk):
    feedback = get_object_or_404(Feedback.objects.select_related("author"), pk=pk)
    return render(
        request,
        "tracker/feedback_detail.html",
        {
            "feedback": feedback,
            "vendor_tickets": feedback.vendor_tickets.all(),
            "attachments": feedback.attachments.all(),
            "timeline": build_timeline(feedback),
            "back_url": request.session.get("feedback_list_url") or reverse("feedback_list"),
        },
    )
