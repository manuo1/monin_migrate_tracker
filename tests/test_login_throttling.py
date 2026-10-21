from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery"


@pytest.fixture
def account():
    return get_user_model().objects.create_user(username="alice", password=PASSWORD)


def attempt(client, username, password, ip="10.0.0.1"):
    return client.post(reverse("login"), {"username": username, "password": password}, REMOTE_ADDR=ip)


def fail(client, username, times, ip="10.0.0.1"):
    for _ in range(times):
        attempt(client, username, "wrong-password", ip)


def test_default_limits(settings):
    assert settings.AXES_FAILURE_LIMIT == 5
    assert timedelta(minutes=15) == settings.AXES_COOLOFF_TIME
    assert settings.AXES_LOCKOUT_PARAMETERS == ["username"]


def test_login_still_works_below_the_limit(client, account):
    fail(client, "alice", 4)
    response = attempt(client, "alice", PASSWORD)
    assert response.status_code == 302


def test_account_is_locked_after_five_failures_even_with_the_right_password(client, account):
    fail(client, "alice", 5)
    response = attempt(client, "alice", PASSWORD)
    assert response.status_code == 429
    assert "_auth_user_id" not in client.session
    assert "verrouillé" in response.content.decode()


def test_lock_follows_the_username_whatever_the_ip(client, account):
    for index in range(5):
        attempt(client, "alice", "wrong-password", ip=f"10.0.1.{index}")
    response = attempt(client, "alice", PASSWORD, ip="10.0.2.99")
    assert response.status_code == 429


def test_other_accounts_are_not_locked(client, account):
    get_user_model().objects.create_user(username="bob", password=PASSWORD)
    fail(client, "alice", 5)
    assert attempt(client, "bob", PASSWORD).status_code == 302


def test_a_successful_login_resets_the_counter(client, account):
    fail(client, "alice", 4)
    assert attempt(client, "alice", PASSWORD).status_code == 302
    client.logout()
    fail(client, "alice", 4)
    assert attempt(client, "alice", PASSWORD).status_code == 302


def test_limit_is_configurable(client, account, settings):
    settings.AXES_FAILURE_LIMIT = 2
    fail(client, "alice", 2)
    assert attempt(client, "alice", PASSWORD).status_code == 429
