import re

import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory
from tracker.middleware import CONTENT_SECURITY_POLICY

pytestmark = pytest.mark.django_db

INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)", re.IGNORECASE)
INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


def test_policy_forbids_inline_scripts_and_cdn():
    script_src = next(d for d in CONTENT_SECURITY_POLICY.split("; ") if d.startswith("script-src"))
    assert script_src == "script-src 'self'"
    assert "http" not in CONTENT_SECURITY_POLICY


def test_policy_header_is_sent_on_application_pages(client):
    response = client.get(reverse("login"))

    assert response["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


def test_policy_header_is_not_sent_on_the_admin(client):
    response = client.get("/admin/login/")

    assert "Content-Security-Policy" not in response


def test_pages_contain_no_inline_script_nor_event_handler(client):
    staff = StaffFactory()
    client.force_login(staff)
    feedback = FeedbackFactory()
    urls = [
        reverse("feedback_list"),
        f"/feedbacks/{feedback.pk}/",
        "/feedbacks/new/",
        reverse("feedback_edit", args=[feedback.pk]),
        reverse("vendor_ticket_list"),
        "/vendor-tickets/new/",
        f"/vendor-tickets/new/?feedback={feedback.pk}",
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
        html = response.content.decode()
        assert not INLINE_SCRIPT.search(html), f"inline <script> in {url}"
        assert not INLINE_HANDLER.search(html), f"inline event handler in {url}"
