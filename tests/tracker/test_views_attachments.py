import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory

pytestmark = pytest.mark.django_db


def make_attachment(name="shot.png", content=b"file-bytes"):
    return FeedbackFactory().attachments.create(file=SimpleUploadedFile(name, content))


def body(response):
    return b"".join(response.streaming_content)


@pytest.mark.parametrize("role", ["anonymous", "user", "staff"])
def test_attachment_access_matrix(client, role):
    attachment = make_attachment()
    if role != "anonymous":
        client.force_login({"user": UserFactory, "staff": StaffFactory}[role]())

    response = client.get(reverse("attachment_file", args=[attachment.pk]))

    if role == "anonymous":
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    else:
        assert response.status_code == 200
        assert body(response) == b"file-bytes"


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("shot.png", "image/png"), ("shot.jpg", "image/jpeg"), ("video.mp4", "video/mp4"), ("doc.pdf", "application/pdf")],
)
def test_safe_types_are_displayed_inline(client, filename, content_type):
    client.force_login(UserFactory())
    response = client.get(reverse("attachment_file", args=[make_attachment(filename).pk]))
    assert response["Content-Type"] == content_type
    assert response["Content-Disposition"].startswith("inline")


@pytest.mark.parametrize(
    "filename", ["page.html", "image.svg", "script.js", "notes.docx", "archive.zip", "noextension"]
)
def test_other_types_are_forced_to_download(client, filename):
    client.force_login(UserFactory())
    response = client.get(reverse("attachment_file", args=[make_attachment(filename).pk]))
    assert response["Content-Disposition"].startswith("attachment")


def test_unknown_attachment_is_a_404(client):
    client.force_login(UserFactory())
    assert client.get(reverse("attachment_file", args=[999999])).status_code == 404


def test_attachment_whose_file_vanished_from_disk_is_a_404(client):
    client.force_login(UserFactory())
    attachment = make_attachment()
    default_storage.delete(attachment.file.name)
    assert client.get(reverse("attachment_file", args=[attachment.pk])).status_code == 404


def test_attachments_are_not_reachable_through_a_public_media_url(client):
    attachment = make_attachment()
    assert client.get(f"/media/{attachment.file.name}").status_code == 404
