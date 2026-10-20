import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker.statuses import NEW, SENT_TO_VENDOR, VENDOR_CLOSED

pytestmark = pytest.mark.django_db


def _url(feedback):
    return reverse("vendor_ticket_associate", args=[feedback.pk])


def _checkbox(ticket):
    return f'name="tickets" value="{ticket.pk}"'


@pytest.fixture
def staff(client):
    account = StaffFactory()
    client.force_login(account)
    return account


# --- Permission matrix: anonymous / user / staff ---


def test_anonymous_is_redirected_to_login(client):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    for response in (client.get(_url(feedback)), client.post(_url(feedback), {"tickets": [ticket.pk]})):
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    assert not feedback.vendor_tickets.exists()


def test_non_staff_cannot_associate_even_on_their_own_feedback(client):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    client.force_login(feedback.author)
    assert client.get(_url(feedback)).status_code == 403
    assert client.post(_url(feedback), {"tickets": [ticket.pk]}).status_code == 403
    assert not feedback.vendor_tickets.exists()


def test_unknown_feedback_is_a_404(staff, client):
    assert client.get(reverse("vendor_ticket_associate", args=[999999])).status_code == 404


# --- Page ---


def test_page_shows_the_feedback_and_the_tickets_with_a_checkbox_each(staff, client):
    feedback = FeedbackFactory(page="Clients", description="Description du retour")
    free = VendorTicketFactory(ref="TEST-1")

    response = client.get(_url(feedback))

    assert response.status_code == 200
    assert response.context["feedback"] == feedback
    content = response.content.decode()
    assert "Description du retour" in content
    assert "TEST-1" in content
    assert _checkbox(free) in content


def test_already_linked_tickets_have_no_checkbox(staff, client):
    feedback = FeedbackFactory()
    linked = VendorTicketFactory(ref="TEST-LINKED")
    free = VendorTicketFactory(ref="TEST-FREE")
    feedback.vendor_tickets.add(linked)

    response = client.get(_url(feedback))

    content = response.content.decode()
    assert _checkbox(linked) not in content
    assert _checkbox(free) in content
    assert response.context["already"] == {linked.pk}


def test_page_reuses_the_vendor_ticket_filters(staff, client):
    feedback = FeedbackFactory()
    wanted = VendorTicketFactory(ref="TEST-A", status=VENDOR_CLOSED, title="Montant erroné")
    VendorTicketFactory(ref="TEST-B", status=VENDOR_CLOSED, title="Autre sujet")
    VendorTicketFactory(ref="TEST-C", title="Montant erroné")

    response = client.get(_url(feedback), {"status": VENDOR_CLOSED, "q": "montant"})

    assert [t.ref for t in response.context["tickets"]] == [wanted.ref]


def test_the_associate_page_does_not_overwrite_the_remembered_list_url(staff, client):
    feedback = FeedbackFactory()
    client.get(reverse("vendor_ticket_list"), {"status": VENDOR_CLOSED})
    client.get(_url(feedback), {"q": "something"})
    assert client.session["vendor_ticket_list_url"] == reverse("vendor_ticket_list") + "?status=closed"


# --- Association ---


def test_checked_tickets_are_added_to_the_existing_links(staff, client):
    feedback = FeedbackFactory(status=NEW)
    existing, first, second = VendorTicketFactory(), VendorTicketFactory(), VendorTicketFactory()
    feedback.vendor_tickets.add(existing)

    response = client.post(_url(feedback), {"tickets": [first.pk, second.pk]}, follow=True)

    assert response.redirect_chain == [(reverse("feedback_detail", args=[feedback.pk]), 302)]
    feedback.refresh_from_db()
    assert set(feedback.vendor_tickets.all()) == {existing, first, second}
    content = response.content.decode()
    assert f"2 ticket(s) Aptean associé(s) au ticket Monin #{feedback.pk}." in content
    assert "Le ticket Monin passe en « Transmis Aptean »." in content
    assert feedback.status == SENT_TO_VENDOR  # rule T1
    assert first.events.exists()  # traced on the vendor ticket side too


def test_no_status_message_when_the_status_does_not_move(staff, client):
    feedback = FeedbackFactory(status=SENT_TO_VENDOR)
    ticket = VendorTicketFactory()
    response = client.post(_url(feedback), {"tickets": [ticket.pk]}, follow=True)
    assert "Le ticket Monin passe en" not in response.content.decode()


def test_nothing_checked_is_refused(staff, client):
    feedback = FeedbackFactory()
    response = client.post(_url(feedback), {}, follow=True)
    assert response.redirect_chain == [(_url(feedback), 302)]
    assert "Aucun ticket Aptean coché." in response.content.decode()
    assert not feedback.vendor_tickets.exists()


def test_already_linked_tickets_are_not_counted_again(staff, client):
    feedback = FeedbackFactory()
    linked, new = VendorTicketFactory(), VendorTicketFactory()
    feedback.vendor_tickets.add(linked)

    response = client.post(_url(feedback), {"tickets": [linked.pk, new.pk]}, follow=True)

    assert "1 ticket(s) Aptean associé(s)" in response.content.decode()
    assert set(feedback.vendor_tickets.all()) == {linked, new}


def test_only_already_linked_tickets_checked_is_refused(staff, client):
    feedback = FeedbackFactory()
    linked = VendorTicketFactory()
    feedback.vendor_tickets.add(linked)
    response = client.post(_url(feedback), {"tickets": [linked.pk]}, follow=True)
    assert "Aucun ticket Aptean coché." in response.content.decode()


def test_unknown_and_malformed_ids_are_ignored(staff, client):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    client.post(_url(feedback), {"tickets": ["abc", "999999", str(ticket.pk)]})
    assert list(feedback.vendor_tickets.all()) == [ticket]


# --- Entry points ---


def test_feedback_detail_offers_the_association_to_staff_only(client):
    feedback = FeedbackFactory()

    client.force_login(feedback.author)
    assert _url(feedback) not in client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()

    client.force_login(StaffFactory())
    assert _url(feedback) in client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()


def test_vendor_ticket_badges_on_the_feedback_detail_link_to_the_ticket(client):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    feedback.vendor_tickets.add(ticket)
    client.force_login(feedback.author)
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert reverse("vendor_ticket_detail", args=[ticket.pk]) in content


def test_other_users_cannot_see_the_association_checkboxes_on_the_plain_list(client):
    VendorTicketFactory()
    client.force_login(UserFactory())
    assert 'name="tickets"' not in client.get(reverse("vendor_ticket_list")).content.decode()
