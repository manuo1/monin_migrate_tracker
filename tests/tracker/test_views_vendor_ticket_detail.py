from datetime import UTC, date, datetime

import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker.models import VendorTicketEvent
from tracker.statuses import VENDOR_IN_PROGRESS

pytestmark = pytest.mark.django_db


def detail_url(ticket):
    return reverse("vendor_ticket_detail", args=[ticket.pk])


# --- Access: login required, then open to every logged-in user (read only) ---


@pytest.mark.parametrize("role", ["anonymous", "user", "staff"])
def test_vendor_ticket_detail_access_matrix(client, role):
    ticket = VendorTicketFactory()
    if role == "user":
        client.force_login(UserFactory())
    elif role == "staff":
        client.force_login(StaffFactory())

    response = client.get(detail_url(ticket))

    if role == "anonymous":
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    else:
        assert response.status_code == 200


def test_unknown_vendor_ticket_is_a_404(client):
    client.force_login(UserFactory())
    assert client.get(reverse("vendor_ticket_detail", args=[999999])).status_code == 404


# --- Content ---


def test_detail_shows_the_ticket_fields(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory(
        ref="TEST-55",
        title="Titre du ticket",
        description="Ligne 1\nLigne 2",
        page="Clients",
        tab="Adresses",
        status=VENDOR_IN_PROGRESS,
        created_on=date(2026, 3, 14),
    )
    content = client.get(detail_url(ticket)).content.decode()
    for expected in (
        "TEST-55",
        "Titre du ticket",
        "Ligne 1",
        "Ligne 2",
        "Clients",
        "Adresses",
        "En cours",
        "14/03/2026",
    ):
        assert expected in content


def test_detail_of_a_ticket_without_reference_shows_the_placeholder(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory(ref=None)
    assert f"Sans réf. (#{ticket.pk})" in client.get(detail_url(ticket)).content.decode()


def test_detail_lists_the_linked_feedbacks_with_a_link_to_each(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    linked = FeedbackFactory(description="Retour lié visible")
    linked.vendor_tickets.add(ticket)
    FeedbackFactory(description="Retour non lié")

    response = client.get(detail_url(ticket))

    assert [f.pk for f in response.context["feedbacks"]] == [linked.pk]
    content = response.content.decode()
    assert reverse("feedback_detail", args=[linked.pk]) in content
    assert "Retour lié visible" in content
    assert "Retour non lié" not in content


def test_detail_without_linked_feedback_says_so(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    assert "aucun ticket lié" in client.get(detail_url(ticket)).content.decode()


def test_detail_shows_the_history_newest_first(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    author = UserFactory(username="alice")
    VendorTicketEvent.objects.create(
        ticket=ticket, author=author, text="Premier événement", date=datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    )
    VendorTicketEvent.objects.create(
        ticket=ticket, author=author, text="Second événement", date=datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
    )

    response = client.get(detail_url(ticket))

    assert [e.text for e in response.context["events"]] == ["Second événement", "Premier événement"]
    content = response.content.decode()
    assert "alice" in content
    assert content.index("Second événement") < content.index("Premier événement")


def test_detail_without_event_says_so(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    assert "Aucun événement." in client.get(detail_url(ticket)).content.decode()


def test_the_jira_link_is_shown_to_staff_only(client):
    ticket = VendorTicketFactory(ref="TEST-88")
    jira_url = "https://jira.example.com/browse/TEST-88"
    client.force_login(UserFactory())
    assert jira_url not in client.get(detail_url(ticket)).content.decode()
    client.force_login(StaffFactory())
    assert jira_url in client.get(detail_url(ticket)).content.decode()


# --- Navigation ---


def test_back_button_returns_to_the_list_with_its_filters(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    client.get(reverse("vendor_ticket_list"), {"status": "closed", "sort": "page"})

    response = client.get(detail_url(ticket))

    assert response.context["back_url"] == reverse("vendor_ticket_list") + "?status=closed&sort=page"


def test_back_button_defaults_to_the_plain_list(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    assert client.get(detail_url(ticket)).context["back_url"] == reverse("vendor_ticket_list")


def test_the_reference_in_the_list_links_to_the_detail(client):
    client.force_login(UserFactory())
    ticket = VendorTicketFactory()
    assert detail_url(ticket) in client.get(reverse("vendor_ticket_list")).content.decode()
