import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory
from tracker import services

pytestmark = pytest.mark.django_db


# --- Service ---


def test_add_comment_strips_the_text_and_keeps_the_author():
    feedback, author = FeedbackFactory(), UserFactory()
    comment = services.add_comment(feedback, author, "  Précision utile \n")
    assert comment.text == "Précision utile"
    assert comment.author == author
    assert list(feedback.comments.all()) == [comment]


# --- View: anonymous / user / author / staff ---


@pytest.mark.parametrize("role", ["user", "author", "staff"])
def test_any_logged_in_user_can_comment(client, role):
    feedback = FeedbackFactory()
    accounts = {"user": UserFactory(), "author": feedback.author, "staff": StaffFactory()}
    client.force_login(accounts[role])

    response = client.post(reverse("add_comment", args=[feedback.pk]), {"text": "Mon commentaire"})

    assert response.status_code == 302
    assert response.url == reverse("feedback_detail", args=[feedback.pk])
    comment = feedback.comments.get()
    assert (comment.text, comment.author) == ("Mon commentaire", accounts[role])


def test_anonymous_cannot_comment(client):
    feedback = FeedbackFactory()
    response = client.post(reverse("add_comment", args=[feedback.pk]), {"text": "Intrus"})
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))
    assert not feedback.comments.exists()


def test_an_empty_comment_is_refused_with_a_message(client):
    feedback = FeedbackFactory()
    client.force_login(UserFactory())
    response = client.post(reverse("add_comment", args=[feedback.pk]), {"text": "   "}, follow=True)
    assert not feedback.comments.exists()
    assert "Le commentaire est vide." in response.content.decode()


def test_comment_view_is_post_only(client):
    feedback = FeedbackFactory()
    client.force_login(UserFactory())
    assert client.get(reverse("add_comment", args=[feedback.pk])).status_code == 405


def test_commenting_an_unknown_feedback_is_a_404(client):
    client.force_login(UserFactory())
    assert client.post(reverse("add_comment", args=[999999]), {"text": "x"}).status_code == 404


def test_detail_shows_the_comment_form_and_the_posted_comment(client):
    feedback = FeedbackFactory()
    client.force_login(UserFactory())
    client.post(reverse("add_comment", args=[feedback.pk]), {"text": "Visible dans l'historique"})
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert "Visible dans l&#x27;historique" in content
    assert reverse("add_comment", args=[feedback.pk]) in content
