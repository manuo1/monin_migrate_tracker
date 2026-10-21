import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, VendorTicketFactory
from tracker import services
from tracker.statuses import CLOSED, IN_ANALYSIS, NEW

pytestmark = pytest.mark.django_db


def _url(feedback):
    return reverse("feedback_triage", args=[feedback.pk])


def _post_data(feedback, state, **overrides):
    data = {
        "status": feedback.status,
        "closure_reason": feedback.closure_reason,
        "explanation": "",
        "vendor_tickets": [t.pk for t in feedback.vendor_tickets.all()],
        "state": state,
    }
    data.update(overrides)
    return data


# --- Fingerprint ---


def test_state_is_stable_for_an_unchanged_feedback():
    feedback = FeedbackFactory()
    assert services.triage_state(feedback) == services.triage_state(feedback)


def test_state_changes_with_status_closure_reason_and_vendor_links():
    feedback = FeedbackFactory()
    initial = services.triage_state(feedback)

    feedback.status = IN_ANALYSIS
    after_status = services.triage_state(feedback)
    feedback.closure_reason = "rejected"
    after_reason = services.triage_state(feedback)
    feedback.vendor_tickets.add(VendorTicketFactory())
    after_link = services.triage_state(feedback)

    assert len({initial, after_status, after_reason, after_link}) == 4


def test_state_ignores_comments():
    feedback = FeedbackFactory()
    before = services.triage_state(feedback)
    services.add_comment(feedback, StaffFactory(), "Un commentaire")
    assert services.triage_state(feedback) == before


# --- Service ---


def test_service_refuses_a_stale_state_and_writes_nothing():
    feedback = FeedbackFactory()
    staff = StaffFactory()
    stale = services.triage_state(feedback)
    other = type(feedback).objects.get(pk=feedback.pk)
    services.change_status(other, IN_ANALYSIS, staff)

    with pytest.raises(services.StaleStateError):
        services.triage(
            feedback,
            staff,
            status=CLOSED,
            closure_reason="rejected",
            explanation="Hors périmètre",
            vendor_tickets=[],
            expected_state=stale,
        )

    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS
    assert not feedback.comments.exists()


def test_service_accepts_the_current_state():
    feedback = FeedbackFactory()
    services.triage(
        feedback,
        StaffFactory(),
        status=IN_ANALYSIS,
        closure_reason="",
        explanation="",
        vendor_tickets=[],
        expected_state=services.triage_state(feedback),
    )
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS


# --- View ---


def test_detail_embeds_the_current_state_for_staff(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert f'name="state" value="{services.triage_state(feedback)}"' in content


def test_a_stale_post_is_refused_with_a_409_and_changes_nothing(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    stale = services.triage_state(feedback)
    ticket = VendorTicketFactory()

    # Another staff member triages first: status moves and a vendor ticket is linked.
    client.post(_url(feedback), _post_data(feedback, stale, status=IN_ANALYSIS, vendor_tickets=[ticket.pk]))
    events_before = feedback.events.count()

    # The first form is submitted afterwards, with its outdated fingerprint.
    response = client.post(
        _url(feedback), _post_data(feedback, stale, status=CLOSED, closure_reason="rejected", explanation="  Ma note ")
    )

    assert response.status_code == 409
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS  # set by the first triage; the stale post did not touch it
    assert feedback.closure_reason == ""
    assert not feedback.comments.exists()
    assert feedback.events.count() == events_before
    content = response.content.decode()
    assert "modifié entre-temps" in content
    assert "Ma note" in content  # the typed explanation is kept
    assert f'name="state" value="{services.triage_state(feedback)}"' in content  # fresh token: retry works


def test_retry_with_the_fresh_token_succeeds(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    stale = services.triage_state(feedback)
    client.post(_url(feedback), _post_data(feedback, stale, status=IN_ANALYSIS))

    fresh = services.triage_state(type(feedback).objects.get(pk=feedback.pk))
    response = client.post(_url(feedback), _post_data(feedback, fresh, status=CLOSED, closure_reason="rejected"))

    assert response.status_code == 302
    feedback.refresh_from_db()
    assert feedback.status == CLOSED


def test_a_retest_answer_made_meanwhile_makes_the_triage_stale(client):
    feedback = FeedbackFactory(status="retest_user")
    staff = StaffFactory()
    client.force_login(staff)
    stale = services.triage_state(feedback)
    services.answer_retest(feedback, feedback.author, "ok")

    response = client.post(_url(feedback), _post_data(feedback, stale, status=CLOSED))

    assert response.status_code == 409
    feedback.refresh_from_db()
    assert feedback.status == "test_passed"


def test_a_post_without_state_is_invalid(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    data = _post_data(feedback, "", status=CLOSED)
    del data["state"]

    response = client.post(_url(feedback), data)

    assert response.status_code == 200
    feedback.refresh_from_db()
    assert feedback.status == NEW
