import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker import services
from tracker.statuses import CLOSED, IN_ANALYSIS, NEW, RETEST_USER, SENT_TO_VENDOR

pytestmark = pytest.mark.django_db


def _url(feedback):
    return reverse("feedback_triage", args=[feedback.pk])


def _data(feedback, **overrides):
    data = {
        "status": feedback.status,
        "closure_reason": feedback.closure_reason,
        "explanation": "",
        "vendor_tickets": [t.pk for t in feedback.vendor_tickets.all()],
        "state": services.triage_state(feedback),
    }
    data.update(overrides)
    return data


# --- Permission matrix: anonymous / user / author / staff ---


def test_anonymous_is_redirected_to_login(client):
    feedback = FeedbackFactory()
    response = client.post(_url(feedback), _data(feedback, status=CLOSED))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))
    feedback.refresh_from_db()
    assert feedback.status == NEW


@pytest.mark.parametrize("role", ["user", "author"])
def test_non_staff_cannot_triage(client, role):
    feedback = FeedbackFactory()
    client.force_login(UserFactory() if role == "user" else feedback.author)

    response = client.post(_url(feedback), _data(feedback, status=CLOSED))

    assert response.status_code == 403
    feedback.refresh_from_db()
    assert feedback.status == NEW
    assert not feedback.comments.exists()


def test_triage_is_post_only(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    assert client.get(_url(feedback)).status_code == 405


def test_triage_of_an_unknown_feedback_is_a_404(client):
    client.force_login(StaffFactory())
    assert client.post(reverse("feedback_triage", args=[999999]), {"status": NEW}).status_code == 404


# --- Status, closure reason, explanation ---


def test_staff_changes_status_and_it_is_traced(client):
    feedback = FeedbackFactory()
    staff = StaffFactory()
    client.force_login(staff)

    response = client.post(_url(feedback), _data(feedback, status=IN_ANALYSIS))

    assert response.status_code == 302
    assert response.url == reverse("feedback_detail", args=[feedback.pk])
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS
    last = feedback.status_history.last()
    assert (last.status, last.author) == (IN_ANALYSIS, staff)


def test_closing_with_a_reason_and_an_explanation(client):
    feedback = FeedbackFactory()
    staff = StaffFactory()
    client.force_login(staff)

    client.post(
        _url(feedback), _data(feedback, status=CLOSED, closure_reason="rejected", explanation="  Hors périmètre ")
    )

    feedback.refresh_from_db()
    assert (feedback.status, feedback.closure_reason) == (CLOSED, "rejected")
    comment = feedback.comments.get()
    assert (comment.text, comment.author) == ("Hors périmètre", staff)
    assert any(e.text.startswith("Closure reason") for e in feedback.events.all())


def test_unchanged_status_adds_no_status_row(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    client.post(_url(feedback), _data(feedback))
    assert feedback.status_history.count() == 0  # the factory writes no creation row; no new row either
    assert not feedback.comments.exists()


def test_any_status_can_be_chosen_without_validation(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    client.post(_url(feedback), _data(feedback, status=RETEST_USER, closure_reason=""))
    feedback.refresh_from_db()
    assert feedback.status == RETEST_USER


# --- Vendor ticket links (rule T1) ---


def test_linking_a_vendor_ticket_to_a_new_feedback_transmits_it(client):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    client.force_login(StaffFactory())

    response = client.post(_url(feedback), _data(feedback, vendor_tickets=[ticket.pk]), follow=True)

    feedback.refresh_from_db()
    assert list(feedback.vendor_tickets.all()) == [ticket]
    assert feedback.status == SENT_TO_VENDOR
    assert "Le ticket passe en" in response.content.decode()
    assert any(e.text == f"Aptean ticket added: {ticket.label}" for e in feedback.events.all())


def test_status_chosen_by_staff_is_respected_when_linking(client):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    client.force_login(StaffFactory())

    client.post(_url(feedback), _data(feedback, status=IN_ANALYSIS, vendor_tickets=[ticket.pk]))

    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS
    assert list(feedback.vendor_tickets.all()) == [ticket]


def test_unlinking_vendor_tickets(client):
    feedback = FeedbackFactory(status=SENT_TO_VENDOR)
    ticket = VendorTicketFactory()
    feedback.vendor_tickets.add(ticket)
    client.force_login(StaffFactory())

    client.post(_url(feedback), _data(feedback, vendor_tickets=[]))

    feedback.refresh_from_db()
    assert not feedback.vendor_tickets.exists()
    assert feedback.status == SENT_TO_VENDOR
    assert any(e.text == f"Aptean ticket removed: {ticket.label}" for e in feedback.events.all())


# --- Invalid input ---


@pytest.mark.parametrize(
    "overrides",
    [{"status": "nope"}, {"closure_reason": "nope"}, {"vendor_tickets": [999999]}],
)
def test_invalid_triage_changes_nothing_and_redisplays_the_page(client, overrides):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())

    response = client.post(_url(feedback), _data(feedback, **overrides))

    assert response.status_code == 200
    assert f"Ticket #{feedback.pk}" in response.content.decode()
    feedback.refresh_from_db()
    assert feedback.status == NEW
    assert not feedback.events.exists()
    assert not feedback.comments.exists()


# --- Detail page ---


def test_detail_shows_the_triage_form_to_staff_only(client):
    feedback = FeedbackFactory()
    link = _url(feedback)

    client.force_login(feedback.author)
    assert link not in client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()

    client.force_login(StaffFactory())
    assert link in client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()


def test_triage_form_is_prefilled_with_the_current_state(client):
    feedback = FeedbackFactory(status=IN_ANALYSIS)
    ticket = VendorTicketFactory()
    feedback.vendor_tickets.add(ticket)
    client.force_login(StaffFactory())

    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()

    assert f'<option value="{IN_ANALYSIS}" selected>' in content
    assert f'<option value="{ticket.pk}" selected>' in content
