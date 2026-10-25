from datetime import date

import pytest
from django.urls import reverse

from tests.tracker.factories import StaffFactory, UserFactory, VendorTicketFactory
from tracker.statuses import VENDOR_IN_PROGRESS, VENDOR_TO_TEST

pytestmark = pytest.mark.django_db


def _url(ticket):
    return reverse("vendor_ticket_edit", args=[ticket.pk])


def _data(ticket, **overrides):
    data = {
        "ref": ticket.ref or "",
        "title": ticket.title,
        "description": ticket.description,
        "page": ticket.page,
        "tab": ticket.tab,
        "status": ticket.status,
        "url": ticket.url,
        "created_on": ticket.created_on.isoformat() if ticket.created_on else "",
    }
    data.update(overrides)
    return data


# --- Permission matrix: anonymous / user / staff ---


def test_anonymous_is_redirected_to_login(client):
    ticket = VendorTicketFactory(title="Avant")
    for response in (client.get(_url(ticket)), client.post(_url(ticket), _data(ticket, title="Hack"))):
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    ticket.refresh_from_db()
    assert ticket.title == "Avant"


def test_non_staff_cannot_edit(client):
    ticket = VendorTicketFactory(title="Avant")
    client.force_login(UserFactory())

    assert client.get(_url(ticket)).status_code == 403
    assert client.post(_url(ticket), _data(ticket, title="Hack")).status_code == 403

    ticket.refresh_from_db()
    assert ticket.title == "Avant"
    assert not ticket.events.exists()


def test_staff_sees_the_form_prefilled(client):
    ticket = VendorTicketFactory(ref="TEST-12", title="Titre", page="Clients", tab="Adresses")
    client.force_login(StaffFactory())
    response = client.get(_url(ticket))
    assert response.status_code == 200
    content = response.content.decode()
    for expected in ('value="TEST-12"', 'value="Titre"', 'value="Clients"', 'value="Adresses"'):
        assert expected in content


def test_edit_unknown_ticket_is_a_404(client):
    client.force_login(StaffFactory())
    assert client.get(reverse("vendor_ticket_edit", args=[999999])).status_code == 404


def test_detail_shows_the_edit_link_to_staff_only(client):
    ticket = VendorTicketFactory()
    detail = reverse("vendor_ticket_detail", args=[ticket.pk])

    client.force_login(UserFactory())
    assert _url(ticket) not in client.get(detail).content.decode()

    client.force_login(StaffFactory())
    assert _url(ticket) in client.get(detail).content.decode()


# --- Saving ---


def test_staff_edit_saves_and_traces_each_changed_field(client):
    ticket = VendorTicketFactory(ref=None, title="Avant", description="", page="", tab="", status="")
    staff = StaffFactory()
    client.force_login(staff)

    response = client.post(
        _url(ticket),
        _data(
            ticket,
            title="Après",
            description="Détail",
            page="Clients",
            tab="Adresses",
            status=VENDOR_TO_TEST,
            created_on="2026-03-14",
        ),
    )

    assert response.status_code == 302
    assert response.url == reverse("vendor_ticket_detail", args=[ticket.pk])
    ticket.refresh_from_db()
    assert (ticket.title, ticket.description, ticket.page, ticket.tab, ticket.status, ticket.created_on) == (
        "Après",
        "Détail",
        "Clients",
        "Adresses",
        VENDOR_TO_TEST,
        date(2026, 3, 14),
    )
    events = list(ticket.events.all())
    assert len(events) == 6
    assert all(e.author == staff for e in events)
    assert any(e.text.startswith("Title") and "Après" in e.text for e in events)
    assert any(e.text.startswith("Status") and "To test" in e.text for e in events)


def test_unchanged_form_writes_no_history(client):
    ticket = VendorTicketFactory(ref=None)
    client.force_login(StaffFactory())
    response = client.post(_url(ticket), _data(ticket), follow=True)
    assert response.status_code == 200
    assert not ticket.events.exists()
    assert "Aucune modification." in response.content.decode()


def test_changing_the_reference_rebuilds_the_link(client):
    ticket = VendorTicketFactory(ref="TEST-1", url="https://jira.example.com/browse/TEST-1")
    client.force_login(StaffFactory())
    client.post(_url(ticket), _data(ticket, ref="TEST-2", url="https://elsewhere.example.com/x"))
    ticket.refresh_from_db()
    assert ticket.ref == "TEST-2"
    assert ticket.url == "https://jira.example.com/browse/TEST-2"


def test_the_link_is_kept_as_typed_when_there_is_no_reference(client):
    ticket = VendorTicketFactory(ref=None)
    client.force_login(StaffFactory())
    client.post(_url(ticket), _data(ticket, ref="", url="https://jira.example.com/browse/CUSTOM-1"))
    ticket.refresh_from_db()
    assert ticket.ref is None
    assert ticket.url == "https://jira.example.com/browse/CUSTOM-1"


@pytest.mark.parametrize("typed", ["", "  ", "TEST-"])
def test_empty_or_prefix_only_reference_is_stored_as_none(client, typed):
    ticket = VendorTicketFactory(ref="TEST-1")
    client.force_login(StaffFactory())
    client.post(_url(ticket), _data(ticket, ref=typed))
    ticket.refresh_from_db()
    assert ticket.ref is None


def test_several_tickets_can_have_no_reference(client):
    other = VendorTicketFactory(ref=None)
    ticket = VendorTicketFactory(ref="TEST-1")
    client.force_login(StaffFactory())
    response = client.post(_url(ticket), _data(ticket, ref=""))
    assert response.status_code == 302
    ticket.refresh_from_db()
    other.refresh_from_db()
    assert ticket.ref is None and other.ref is None


def test_reference_already_used_by_another_ticket_is_refused(client):
    VendorTicketFactory(ref="TEST-100")
    ticket = VendorTicketFactory(ref="TEST-1")
    client.force_login(StaffFactory())

    response = client.post(_url(ticket), _data(ticket, ref="TEST-100", title="Changé"))

    assert response.status_code == 200
    assert response.context["form"].errors["ref"]
    ticket.refresh_from_db()
    assert (ticket.ref, ticket.title) != ("TEST-100", "Changé")
    assert not ticket.events.exists()


def test_unknown_status_is_refused(client):
    ticket = VendorTicketFactory(status=VENDOR_IN_PROGRESS)
    client.force_login(StaffFactory())
    response = client.post(_url(ticket), _data(ticket, status="nonsense"))
    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == VENDOR_IN_PROGRESS


def test_invalid_date_is_refused_and_nothing_is_saved(client):
    ticket = VendorTicketFactory(title="Avant")
    client.force_login(StaffFactory())
    response = client.post(_url(ticket), _data(ticket, title="Après", created_on="not a date"))
    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.title == "Avant"
    assert not ticket.events.exists()
