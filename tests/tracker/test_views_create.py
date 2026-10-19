import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, UserFactory
from tracker.choices import FeedbackType
from tracker.models import Feedback
from tracker.statuses import NEW

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(client):
    account = UserFactory()
    client.force_login(account)
    return account


def upload(name="shot.png"):
    return SimpleUploadedFile(name, b"content")


def valid_data(**overrides):
    data = {"type": "bug", "page": "Clients", "tab": "Adresses", "article_id": "A-1", "description": "Montant faux"}
    data.update(overrides)
    return data


# --- Access ---


def test_anonymous_is_sent_to_login(client):
    for method in (client.get, client.post):
        response = method(reverse("feedback_create"))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    assert not Feedback.objects.exists()


def test_form_is_displayed_to_any_logged_in_user(user, client):
    response = client.get(reverse("feedback_create"))
    assert response.status_code == 200
    assert response.context["form"].initial["type"] == FeedbackType.BUG


def test_type_choices_have_no_empty_option(user, client):
    choices = client.get(reverse("feedback_create")).context["form"].fields["type"].choices
    assert [value for value, _ in choices] == FeedbackType.values


def test_type_can_be_preselected_from_the_url_and_unknown_values_are_ignored(user, client):
    url = reverse("feedback_create")
    assert client.get(url, {"type": "suggestion"}).context["form"].initial["type"] == "suggestion"
    assert client.get(url, {"type": "nonsense"}).context["form"].initial["type"] == FeedbackType.BUG


# --- Creation ---


def test_creating_a_feedback_sets_author_status_and_first_status_row(user, client):
    response = client.post(reverse("feedback_create"), valid_data())

    feedback = Feedback.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("feedback_detail", args=[feedback.pk])
    assert (feedback.author, feedback.status) == (user, NEW)
    assert (feedback.page, feedback.tab, feedback.article_id) == ("Clients", "Adresses", "A-1")
    assert [row.status for row in feedback.status_history.all()] == [NEW]


def test_creating_with_files_stores_the_attachments(user, client):
    client.post(reverse("feedback_create"), valid_data(files=[upload("a.png"), upload("b.png")]))
    assert Feedback.objects.get().attachments.count() == 2


@pytest.mark.parametrize("missing", ["page", "description", "type"])
def test_required_fields_are_enforced(user, client, missing):
    response = client.post(reverse("feedback_create"), valid_data(**{missing: ""}))
    assert response.status_code == 200
    assert missing in response.context["form"].errors
    assert not Feedback.objects.exists()


def test_tab_and_article_are_optional(user, client):
    client.post(reverse("feedback_create"), valid_data(tab="", article_id=""))
    assert Feedback.objects.count() == 1


# --- Duplicates ---


def test_identical_page_tab_and_description_is_refused_with_a_link_to_the_existing_one(user, client):
    existing = FeedbackFactory(page="Clients", tab="Adresses", description="Montant faux\nsur deux lignes")

    response = client.post(reverse("feedback_create"), valid_data(description="  Montant faux\r\nsur deux lignes "))

    assert response.status_code == 200
    assert Feedback.objects.count() == 1
    assert response.context["form"].duplicate == existing
    assert reverse("feedback_detail", args=[existing.pk]) in response.content.decode()


@pytest.mark.parametrize("overrides", [{"page": "Articles"}, {"tab": "Contacts"}, {"description": "Autre"}])
def test_changing_page_tab_or_description_allows_the_new_feedback(user, client, overrides):
    FeedbackFactory(page="Clients", tab="Adresses", description="Montant faux")
    client.post(reverse("feedback_create"), valid_data(**overrides))
    assert Feedback.objects.count() == 2


# --- Copy ---


def test_copy_prefills_the_form_from_the_source(user, client):
    source = FeedbackFactory(
        type=FeedbackType.SUGGESTION, page="Clients", tab="Adresses", article_id="A-9", description="Idée"
    )
    response = client.get(reverse("feedback_create"), {"copy": source.pk})
    assert response.context["form"].initial == {
        "type": "suggestion",
        "page": "Clients",
        "tab": "Adresses",
        "article_id": "A-9",
        "description": "Idée",
    }
    assert f"Copie du ticket #{source.pk}" in response.content.decode()


def test_copy_lists_the_source_attachments(user, client):
    source = FeedbackFactory()
    attachment = source.attachments.create(file=upload())
    response = client.get(reverse("feedback_create"), {"copy": source.pk})
    assert [c["attachment"] for c in response.context["copied_attachments"]] == [attachment]
    assert 'name="copy_attachment"' in response.content.decode()


def test_unknown_or_invalid_copy_source_is_ignored(user, client):
    for value in ("999999", "abc"):
        response = client.get(reverse("feedback_create"), {"copy": value})
        assert response.status_code == 200
        assert response.context["source"] is None


def test_saving_a_copy_reuses_the_kept_attachments_without_duplicating_files(user, client):
    source = FeedbackFactory()
    kept = source.attachments.create(file=upload("kept.png"))
    dropped = source.attachments.create(file=upload("dropped.png"))
    source.comments.create(author=source.author, text="Commentaire non copié")

    client.post(
        reverse("feedback_create"),
        valid_data(description="Autre description", copy=source.pk, copy_attachment=[kept.pk]),
    )

    copy = Feedback.objects.exclude(pk=source.pk).get()
    assert [a.file.name for a in copy.attachments.all()] == [kept.file.name]
    assert dropped.file.name not in [a.file.name for a in copy.attachments.all()]
    assert not copy.comments.exists()
    assert copy.events.count() == 1  # the copy is traced


def test_saving_an_unchanged_copy_is_refused_as_a_duplicate(user, client):
    source = FeedbackFactory(page="Clients", tab="Adresses", description="Montant faux")
    response = client.post(reverse("feedback_create"), valid_data(copy=source.pk))
    assert response.status_code == 200
    assert Feedback.objects.count() == 1


def test_a_refused_copy_keeps_only_the_still_checked_attachments_on_screen(user, client):
    source = FeedbackFactory(page="Clients", tab="Adresses", description="Montant faux")
    kept = source.attachments.create(file=upload("kept.png"))
    source.attachments.create(file=upload("dropped.png"))

    response = client.post(reverse("feedback_create"), valid_data(copy=source.pk, copy_attachment=[kept.pk]))

    shown = [c["attachment"] for c in response.context["copied_attachments"] if c["checked"]]
    assert shown == [kept]


# --- Entry points ---


def test_the_list_offers_a_create_button_and_the_detail_a_copy_button(user, client):
    feedback = FeedbackFactory(author=user)
    assert reverse("feedback_create") in client.get(reverse("feedback_list")).content.decode()
    detail = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert f"{reverse('feedback_create')}?copy={feedback.pk}" in detail


def test_the_form_lists_my_feedbacks_with_a_copy_button(user, client):
    mine, other = FeedbackFactory(author=user), FeedbackFactory()
    response = client.get(reverse("feedback_create"))
    assert list(response.context["my_feedbacks"]) == [mine]
    assert other not in response.context["my_feedbacks"]
