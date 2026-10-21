from unittest import mock

import pytest
from django.test import Client
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_404_page_is_the_custom_one(client):
    client.force_login(UserFactory())
    response = client.get("/no/such/page/")
    assert response.status_code == 404
    assert "Page introuvable" in response.content.decode()


def test_unknown_feedback_uses_the_custom_404(client):
    client.force_login(UserFactory())
    response = client.get(reverse("feedback_detail", args=[999999]))
    assert response.status_code == 404
    assert "Page introuvable" in response.content.decode()


def test_403_page_is_the_custom_one(client):
    client.force_login(UserFactory())
    response = client.get(reverse("vendor_ticket_create"))
    assert response.status_code == 403
    assert "Accès refusé" in response.content.decode()


def test_csrf_failure_page_is_the_custom_one():
    client = Client(enforce_csrf_checks=True)
    response = client.post(reverse("login"), {"username": "x", "password": "y"})
    assert response.status_code == 403
    assert "Formulaire expiré" in response.content.decode()


def test_500_page_is_the_custom_standalone_one():
    client = Client(raise_request_exception=False)
    client.force_login(StaffFactory())
    feedback = FeedbackFactory()

    with mock.patch("tracker.views.feedbacks.build_timeline", side_effect=RuntimeError("boom")):
        response = client.get(reverse("feedback_detail", args=[feedback.pk]))

    content = response.content.decode()
    assert response.status_code == 500
    assert "Erreur interne" in content
    assert "boom" not in content  # no internal detail leaks to the user
    assert "Content-Security-Policy" in response.headers
