"""Language infrastructure: default language, switch endpoint, navbar switch."""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _html(response):
    return response.content.decode()


def test_default_language_is_french(client):
    response = client.get(reverse("login"))
    assert '<html lang="fr">' in _html(response)
    assert response["Content-Language"] == "fr"


def test_browser_language_is_ignored(client):
    response = client.get(reverse("login"), headers={"accept-language": "en"})
    assert '<html lang="fr">' in _html(response)


def test_set_language_switches_the_interface_and_stays_on_the_page(client):
    response = client.post(reverse("set_language"), {"language": "en", "next": reverse("login")})
    assert response.status_code == 302
    assert response.url == reverse("login")
    assert response.cookies[settings.LANGUAGE_COOKIE_NAME].value == "en"
    assert '<html lang="en">' in _html(client.get(reverse("login")))


def test_the_cookie_is_the_only_thing_that_changes_the_language(client):
    client.post(reverse("set_language"), {"language": "en", "next": reverse("login")})
    response = client.get(reverse("login"), headers={"accept-language": "fr"})
    assert '<html lang="en">' in _html(response)


def test_an_unsupported_language_is_ignored(client):
    client.post(reverse("set_language"), {"language": "de", "next": reverse("login")})
    assert '<html lang="fr">' in _html(client.get(reverse("login")))


def test_an_external_next_url_is_refused(client):
    response = client.post(reverse("set_language"), {"language": "en", "next": "https://evil.example.com/"})
    assert response.url == "/"


def test_the_switch_is_in_the_navbar_for_anonymous_users(client):
    html = _html(client.get(reverse("login")))
    assert f'action="{reverse("set_language")}"' in html
    assert 'name="language" value="fr"' in html
    assert 'name="language" value="en"' in html
    assert f'name="next" value="{reverse("login")}"' in html


def test_the_switch_is_in_the_navbar_for_logged_in_users(client):
    user = get_user_model().objects.create_user("someone", password="x")  # noqa: S106
    client.force_login(user)
    html = _html(client.get(reverse("feedback_list")))
    assert f'action="{reverse("set_language")}"' in html
    assert 'name="language" value="en"' in html
