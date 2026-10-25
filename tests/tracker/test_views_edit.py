import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory
from tracker.choices import FeedbackType

pytestmark = pytest.mark.django_db


def _url(feedback):
    return reverse("feedback_edit", args=[feedback.pk])


def _data(feedback, **overrides):
    data = {
        "type": feedback.type,
        "page": feedback.page,
        "tab": feedback.tab,
        "article_id": feedback.article_id,
    }
    data.update(overrides)
    return data


# --- Permission matrix: anonymous / user / author / staff ---


def test_anonymous_is_redirected_to_login(client):
    feedback = FeedbackFactory()
    for response in (client.get(_url(feedback)), client.post(_url(feedback), _data(feedback, page="Hack"))):
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    feedback.refresh_from_db()
    assert feedback.page != "Hack"


@pytest.mark.parametrize("role", ["user", "author"])
def test_non_staff_cannot_edit(client, role):
    feedback = FeedbackFactory()
    client.force_login(UserFactory() if role == "user" else feedback.author)

    assert client.get(_url(feedback)).status_code == 403
    assert client.post(_url(feedback), _data(feedback, page="Hack")).status_code == 403

    feedback.refresh_from_db()
    assert feedback.page != "Hack"
    assert not feedback.events.exists()


def test_staff_sees_the_form_prefilled(client):
    feedback = FeedbackFactory(page="Articles", tab="Prix", article_id="A1")
    client.force_login(StaffFactory())
    response = client.get(_url(feedback))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="Articles"' in content
    assert 'value="Prix"' in content
    assert 'value="A1"' in content


def test_edit_unknown_feedback_is_a_404(client):
    client.force_login(StaffFactory())
    assert client.get(reverse("feedback_edit", args=[999999])).status_code == 404


# --- Saving ---


def test_staff_edit_saves_and_traces_each_changed_field(client):
    feedback = FeedbackFactory(page="Articles", tab="", article_id="")
    staff = StaffFactory()
    client.force_login(staff)

    response = client.post(
        _url(feedback),
        _data(feedback, type=FeedbackType.SUGGESTION, page="Clients", tab="Adresses", article_id="C42"),
    )

    assert response.status_code == 302
    assert response.url == reverse("feedback_detail", args=[feedback.pk])
    feedback.refresh_from_db()
    assert (feedback.type, feedback.page, feedback.tab, feedback.article_id) == (
        FeedbackType.SUGGESTION,
        "Clients",
        "Adresses",
        "C42",
    )
    events = list(feedback.events.all())
    assert len(events) == 4
    assert all(e.author == staff for e in events)
    assert any(e.text.startswith("Page modified") and "Clients" in e.text for e in events)


def test_unchanged_form_writes_no_history(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    response = client.post(_url(feedback), _data(feedback), follow=True)
    assert response.status_code == 200
    assert not feedback.events.exists()
    assert "Aucune modification." in response.content.decode()


def test_description_is_read_only(client):
    feedback = FeedbackFactory(description="Texte de l'utilisateur")
    client.force_login(StaffFactory())
    client.post(_url(feedback), _data(feedback, description="Réécrit par le staff"))
    feedback.refresh_from_db()
    assert feedback.description == "Texte de l'utilisateur"
    assert not feedback.events.exists()


def test_status_cannot_be_changed_through_the_edit_form(client):
    feedback = FeedbackFactory()
    client.force_login(StaffFactory())
    client.post(_url(feedback), _data(feedback, status="closed", closure_reason="fixed"))
    feedback.refresh_from_db()
    assert feedback.status == "new"
    assert feedback.closure_reason == ""


def test_invalid_form_is_redisplayed_and_nothing_is_saved(client):
    feedback = FeedbackFactory(page="Articles")
    client.force_login(StaffFactory())
    response = client.post(_url(feedback), _data(feedback, page=""))
    assert response.status_code == 200
    feedback.refresh_from_db()
    assert feedback.page == "Articles"
    assert not feedback.events.exists()


# --- Detail page ---


def test_detail_shows_the_edit_link_to_staff_only(client):
    feedback = FeedbackFactory()
    link = _url(feedback)

    client.force_login(feedback.author)
    assert link not in client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()

    client.force_login(StaffFactory())
    assert link in client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
