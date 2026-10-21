import os

import pytest

from tests.tracker.factories import StaffFactory, UserFactory

# Playwright's sync API runs an event loop in the test thread: Django refuses ORM calls there unless told otherwise.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

PASSWORD = "e2e-password"


@pytest.fixture(autouse=True)
def no_csp_violation(page):
    """Fail any journey during which the browser reports a Content-Security-Policy violation."""
    violations = []
    page.on("console", lambda msg: violations.append(msg.text) if "Content Security Policy" in msg.text else None)
    yield
    assert not violations, violations


def _make(factory):
    account = factory()
    account.set_password(PASSWORD)
    account.save()
    return account


@pytest.fixture
def user(live_server):
    return _make(UserFactory)


@pytest.fixture
def staff(live_server):
    return _make(StaffFactory)


@pytest.fixture
def login(live_server):
    """Log in through the real login form."""

    def _login(page, account):
        page.goto(f"{live_server.url}/login/")
        page.fill("#id_username", account.username)
        page.fill("#id_password", PASSWORD)
        page.get_by_role("button", name="Se connecter").click()
        page.wait_for_url(lambda url: "/login/" not in url)

    return _login


@pytest.fixture
def fill_reference():
    """Fill a page/tab input (Tom Select when the CDN is reachable, plain input otherwise)."""

    def _fill(page, input_id, value):
        control = page.locator(f"#{input_id}-ts-control")
        if control.count():
            control.fill(value)
            control.press("Enter")
        else:
            page.fill(f"#{input_id}", value)

    return _fill
