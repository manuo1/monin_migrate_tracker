import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory
from tracker.choices import ClosureReason
from tracker.statuses import IN_ANALYSIS, RETEST_USER, TEST_FAILED, TEST_PASSED

pytestmark = pytest.mark.django_db


def post_retest(client, feedback, **data):
    return client.post(reverse("retest", args=[feedback.pk]), data)


# --- Permission matrix on a feedback in "retest (user)" ---


@pytest.mark.parametrize(
    ("role", "expected"),
    [("anonymous", 302), ("user", 403), ("author", 302), ("staff", 302)],
)
def test_retest_permission_matrix(client, role, expected):
    feedback = FeedbackFactory(status=RETEST_USER)
    accounts = {"user": UserFactory(), "author": feedback.author, "staff": StaffFactory()}
    if role != "anonymous":
        client.force_login(accounts[role])

    response = post_retest(client, feedback, answer="ok")

    assert response.status_code == expected
    feedback.refresh_from_db()
    assert (feedback.status == TEST_PASSED) is (role in {"author", "staff"})
    if role == "anonymous":
        assert response.url.startswith(reverse("login"))


def test_nobody_can_answer_when_the_feedback_is_not_in_retest_user(client):
    feedback = FeedbackFactory(status=IN_ANALYSIS)
    client.force_login(feedback.author)
    assert post_retest(client, feedback, answer="ok").status_code == 403
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS


def test_retest_view_is_post_only(client):
    feedback = FeedbackFactory(status=RETEST_USER)
    client.force_login(feedback.author)
    assert client.get(reverse("retest", args=[feedback.pk])).status_code == 405


def test_unknown_feedback_is_a_404(client):
    client.force_login(UserFactory())
    assert client.post(reverse("retest", args=[999999]), {"answer": "ok"}).status_code == 404


# --- Answers ---


def test_ok_closes_as_fixed_and_the_comment_is_optional(client):
    feedback = FeedbackFactory(status=RETEST_USER)
    client.force_login(feedback.author)

    response = post_retest(client, feedback, answer="ok", comment="")

    assert response.status_code == 302
    assert response.url == reverse("feedback_detail", args=[feedback.pk])
    feedback.refresh_from_db()
    assert (feedback.status, feedback.closure_reason) == (TEST_PASSED, ClosureReason.FIXED)
    assert not feedback.comments.exists()


def test_ok_with_a_comment_publishes_it(client):
    feedback = FeedbackFactory(status=RETEST_USER)
    client.force_login(feedback.author)
    post_retest(client, feedback, answer="ok", comment="Tout est bon")
    assert feedback.comments.get().text == "Tout est bon"


def test_ko_with_a_comment_marks_the_test_as_failed(client):
    feedback = FeedbackFactory(status=RETEST_USER)
    client.force_login(feedback.author)

    post_retest(client, feedback, answer="ko", comment="Toujours faux")

    feedback.refresh_from_db()
    assert feedback.status == TEST_FAILED
    assert feedback.comments.get().text == "Toujours faux"


def test_ko_without_a_comment_is_refused_and_the_page_is_shown_again(client):
    feedback = FeedbackFactory(status=RETEST_USER)
    client.force_login(feedback.author)

    response = post_retest(client, feedback, answer="ko", comment="   ")

    assert response.status_code == 200
    assert "Un commentaire est obligatoire pour un Test KO" in response.content.decode()
    feedback.refresh_from_db()
    assert feedback.status == RETEST_USER


def test_unknown_answer_changes_nothing(client):
    feedback = FeedbackFactory(status=RETEST_USER)
    client.force_login(feedback.author)
    response = post_retest(client, feedback, answer="maybe", comment="x")
    assert response.status_code == 200
    feedback.refresh_from_db()
    assert feedback.status == RETEST_USER


# --- Display on the detail page ---


@pytest.mark.parametrize(
    ("role", "status", "visible"),
    [
        ("author", RETEST_USER, True),
        ("staff", RETEST_USER, True),
        ("user", RETEST_USER, False),
        ("author", IN_ANALYSIS, False),
    ],
)
def test_retest_block_is_displayed_only_when_the_retest_is_open(client, role, status, visible):
    feedback = FeedbackFactory(status=status)
    accounts = {"user": UserFactory(), "author": feedback.author, "staff": StaffFactory()}
    client.force_login(accounts[role])
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert (reverse("retest", args=[feedback.pk]) in content) is visible
