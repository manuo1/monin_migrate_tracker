import pytest
from django.contrib.staticfiles import finders
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory

pytestmark = pytest.mark.django_db


def upload(name="shot.png"):
    return SimpleUploadedFile(name, b"content")


def login(client, role, feedback):
    accounts = {"user": UserFactory, "author": lambda: feedback.author, "staff": StaffFactory}
    if role != "anonymous":
        client.force_login(accounts[role]())


def post_add(client, feedback, *files):
    return client.post(reverse("add_attachments", args=[feedback.pk]), {"files": list(files)})


# --- Add: author and staff only ---


@pytest.mark.parametrize(
    ("role", "expected"),
    [("anonymous", 302), ("user", 403), ("author", 302), ("staff", 302)],
)
def test_add_attachments_permission_matrix(client, role, expected):
    feedback = FeedbackFactory()
    login(client, role, feedback)

    response = post_add(client, feedback, upload())

    assert response.status_code == expected
    assert feedback.attachments.exists() is (role in {"author", "staff"})
    if role == "anonymous":
        assert response.url.startswith(reverse("login"))


def test_adding_several_files_traces_one_event(client):
    feedback = FeedbackFactory()
    client.force_login(feedback.author)

    response = post_add(client, feedback, upload("a.png"), upload("b.png"))

    assert response.url == reverse("feedback_detail", args=[feedback.pk])
    assert feedback.attachments.count() == 2
    assert feedback.events.count() == 1


def test_adding_without_a_file_shows_an_error(client):
    feedback = FeedbackFactory()
    client.force_login(feedback.author)
    response = client.post(reverse("add_attachments", args=[feedback.pk]), follow=True)
    assert "Aucun fichier sélectionné." in response.content.decode()
    assert not feedback.attachments.exists()


def test_add_attachments_is_post_only(client):
    feedback = FeedbackFactory()
    client.force_login(feedback.author)
    assert client.get(reverse("add_attachments", args=[feedback.pk])).status_code == 405


# --- Remove: staff only, the file stays on disk ---


@pytest.mark.parametrize(
    ("role", "expected"),
    [("anonymous", 302), ("user", 403), ("author", 403), ("staff", 302)],
)
def test_remove_attachment_permission_matrix(client, role, expected):
    feedback = FeedbackFactory()
    attachment = feedback.attachments.create(file=upload())
    login(client, role, feedback)

    response = client.post(reverse("remove_attachment", args=[feedback.pk, attachment.pk]))

    assert response.status_code == expected
    assert feedback.attachments.exists() is (role != "staff")


def test_removing_keeps_the_file_on_disk_and_traces_it(client):
    feedback = FeedbackFactory()
    attachment = feedback.attachments.create(file=upload())
    name = attachment.file.name
    client.force_login(StaffFactory())

    client.post(reverse("remove_attachment", args=[feedback.pk, attachment.pk]))

    assert default_storage.exists(name)
    assert feedback.events.count() == 1


def test_cannot_remove_an_attachment_through_another_feedback(client):
    feedback, other = FeedbackFactory(), FeedbackFactory()
    attachment = other.attachments.create(file=upload())
    client.force_login(StaffFactory())

    response = client.post(reverse("remove_attachment", args=[feedback.pk, attachment.pk]))

    assert response.status_code == 404
    assert other.attachments.exists()


# --- Display on the detail page ---


@pytest.mark.parametrize(
    ("role", "can_add", "can_remove"),
    [("user", False, False), ("author", True, False), ("staff", True, True)],
)
def test_detail_shows_only_the_attachment_actions_the_user_may_use(client, role, can_add, can_remove):
    feedback = FeedbackFactory()
    attachment = feedback.attachments.create(file=upload())
    login(client, role, feedback)

    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()

    assert (reverse("add_attachments", args=[feedback.pk]) in content) is can_add
    assert (reverse("remove_attachment", args=[feedback.pk, attachment.pk]) in content) is can_remove


def test_detail_exposes_attachments_to_the_viewer_through_the_authenticated_url(client):
    feedback = FeedbackFactory()
    attachment = feedback.attachments.create(file=upload("shot.png"))
    client.force_login(StaffFactory())

    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()

    assert 'data-kind="image"' in content
    assert f'data-url="{reverse("attachment_file", args=[attachment.pk])}"' in content
    assert 'id="viewer-delete-form"' in content
    assert "/media/" not in content


def test_viewer_delete_button_is_for_staff_only(client):
    feedback = FeedbackFactory()
    feedback.attachments.create(file=upload())
    client.force_login(feedback.author)
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert 'id="attachment-viewer"' in content
    assert 'id="viewer-delete-form"' not in content


@pytest.mark.parametrize("script", ["tracker/dropzone.js", "tracker/attachment_viewer.js"])
def test_attachment_scripts_are_served_as_static_files(client, script):
    assert finders.find(script)
    feedback = FeedbackFactory()
    client.force_login(feedback.author)
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert f"/static/{script}" in content
