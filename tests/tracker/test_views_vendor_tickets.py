from datetime import date

import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker.statuses import VENDOR_BLOCKED, VENDOR_CLOSED, VENDOR_IN_PROGRESS, VENDOR_TO_TEST

pytestmark = pytest.mark.django_db


def refs(response):
    return [t.ref for t in response.context["tickets"]]


@pytest.fixture
def user(client):
    account = UserFactory()
    client.force_login(account)
    return account


@pytest.fixture
def staff(client):
    account = StaffFactory()
    client.force_login(account)
    return account


# --- Access: login required, then open to every logged-in user (read only) ---


@pytest.mark.parametrize("role", ["anonymous", "user", "staff"])
def test_vendor_ticket_list_access_matrix(client, role):
    if role == "user":
        client.force_login(UserFactory())
    elif role == "staff":
        client.force_login(StaffFactory())

    response = client.get(reverse("vendor_ticket_list"))

    if role == "anonymous":
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    else:
        assert response.status_code == 200


def test_every_vendor_ticket_is_listed_whoever_the_user_is(user, client):
    a, b = VendorTicketFactory(), VendorTicketFactory()
    assert {t.pk for t in client.get(reverse("vendor_ticket_list")).context["tickets"]} == {a.pk, b.pk}


# --- Filters ---


def test_filter_by_status(staff, client):
    wanted = VendorTicketFactory(ref="TEST-A", status=VENDOR_TO_TEST)
    VendorTicketFactory(ref="TEST-B", status=VENDOR_CLOSED)
    VendorTicketFactory(ref="TEST-C", status="")
    assert refs(client.get(reverse("vendor_ticket_list"), {"status": VENDOR_TO_TEST})) == [wanted.ref]


def test_filter_on_tickets_without_status(staff, client):
    VendorTicketFactory(ref="TEST-A", status=VENDOR_TO_TEST)
    wanted = VendorTicketFactory(ref="TEST-B", status="")
    assert refs(client.get(reverse("vendor_ticket_list"), {"status": "none"})) == [wanted.ref]


def test_unknown_status_filter_is_ignored(staff, client):
    ticket = VendorTicketFactory()
    assert refs(client.get(reverse("vendor_ticket_list"), {"status": "nonsense"})) == [ticket.ref]


def test_filter_on_linked_and_unlinked_tickets(staff, client):
    linked = VendorTicketFactory(ref="TEST-LINKED")
    unlinked = VendorTicketFactory(ref="TEST-FREE")
    FeedbackFactory().vendor_tickets.add(linked)
    assert refs(client.get(reverse("vendor_ticket_list"), {"linked": "yes"})) == [linked.ref]
    assert refs(client.get(reverse("vendor_ticket_list"), {"linked": "no"})) == [unlinked.ref]


def test_filter_by_page_and_tab(staff, client):
    wanted = VendorTicketFactory(page="Clients", tab="Adresses")
    VendorTicketFactory(page="Clients", tab="Contacts")
    VendorTicketFactory(page="Articles", tab="Adresses")
    response = client.get(reverse("vendor_ticket_list"), {"page": "Clients", "tab": "Adresses"})
    assert refs(response) == [wanted.ref]


def test_tab_choices_are_limited_to_the_selected_page(staff, client):
    VendorTicketFactory(page="Clients", tab="Adresses")
    VendorTicketFactory(page="Articles", tab="Prix")
    response = client.get(reverse("vendor_ticket_list"), {"page": "Clients"})
    assert response.context["pages"] == ["Articles", "Clients"]
    assert response.context["tabs"] == ["Adresses"]


def test_text_search_covers_ref_title_description_page_and_tab(staff, client):
    by_ref = VendorTicketFactory(ref="ZZ-4242")
    by_title = VendorTicketFactory(title="Montant TTC erroné")
    by_description = VendorTicketFactory(description="Le calcul de la remise est faux")
    by_page = VendorTicketFactory(page="Facturation")
    by_tab = VendorTicketFactory(tab="Échéancier")
    VendorTicketFactory(title="Autre chose")
    url = reverse("vendor_ticket_list")
    assert refs(client.get(url, {"q": "zz-42"})) == [by_ref.ref]
    assert refs(client.get(url, {"q": "montant"})) == [by_title.ref]
    assert refs(client.get(url, {"q": "remise"})) == [by_description.ref]
    assert refs(client.get(url, {"q": "factura"})) == [by_page.ref]
    assert refs(client.get(url, {"q": "chéanc"})) == [by_tab.ref]


# --- Sorting ---


def test_default_sort_is_newest_creation_date_first(staff, client):
    older = VendorTicketFactory(created_on=date(2026, 1, 1))
    newer = VendorTicketFactory(created_on=date(2026, 2, 1))
    assert refs(client.get(reverse("vendor_ticket_list"))) == [newer.ref, older.ref]


def test_tickets_without_creation_date_come_last_in_both_directions(staff, client):
    dated = VendorTicketFactory(created_on=date(2026, 1, 1))
    undated = VendorTicketFactory(created_on=None)
    url = reverse("vendor_ticket_list")
    assert refs(client.get(url, {"sort": "date", "order": "asc"})) == [dated.ref, undated.ref]
    assert refs(client.get(url, {"sort": "date", "order": "desc"})) == [dated.ref, undated.ref]


def test_sort_by_status_follows_the_workflow_order_not_the_alphabet(staff, client):
    blocked = VendorTicketFactory(status=VENDOR_BLOCKED)
    in_progress = VendorTicketFactory(status=VENDOR_IN_PROGRESS)
    closed = VendorTicketFactory(status=VENDOR_CLOSED)
    none = VendorTicketFactory(status="")
    url = reverse("vendor_ticket_list")
    assert refs(client.get(url, {"sort": "status", "order": "asc"})) == [
        in_progress.ref,
        closed.ref,
        blocked.ref,
        none.ref,
    ]


def test_sort_by_reference(staff, client):
    b, a = VendorTicketFactory(ref="TEST-B"), VendorTicketFactory(ref="TEST-A")
    assert refs(client.get(reverse("vendor_ticket_list"), {"sort": "ref", "order": "asc"})) == [a.ref, b.ref]


def test_sort_by_number_of_linked_feedbacks(staff, client):
    none = VendorTicketFactory(ref="TEST-NONE")
    one = VendorTicketFactory(ref="TEST-ONE")
    two = VendorTicketFactory(ref="TEST-TWO")
    FeedbackFactory().vendor_tickets.add(one, two)
    FeedbackFactory().vendor_tickets.add(two)
    response = client.get(reverse("vendor_ticket_list"), {"sort": "feedbacks", "order": "desc"})
    assert refs(response) == [two.ref, one.ref, none.ref]


def test_unknown_sort_falls_back_to_date(staff, client):
    response = client.get(reverse("vendor_ticket_list"), {"sort": "nonsense"})
    assert response.status_code == 200
    assert response.context["sort"] == "date"


# --- Navigation and rendering ---


def test_the_list_url_is_remembered_for_the_back_button(staff, client):
    client.get(reverse("vendor_ticket_list"), {"status": VENDOR_CLOSED, "sort": "page"})
    assert client.session["vendor_ticket_list_url"] == reverse("vendor_ticket_list") + "?status=closed&sort=page"


def test_the_navigation_links_to_the_vendor_ticket_list(user, client):
    content = client.get(reverse("feedback_list")).content.decode()
    assert reverse("vendor_ticket_list") in content


def test_list_renders_the_ticket_its_status_and_its_linked_feedbacks(user, client):
    ticket = VendorTicketFactory(ref="TEST-77", title="Titre visible", status=VENDOR_IN_PROGRESS)
    feedback = FeedbackFactory()
    feedback.vendor_tickets.add(ticket)
    content = client.get(reverse("vendor_ticket_list")).content.decode()
    assert "TEST-77" in content
    assert "Titre visible" in content
    assert "En cours" in content
    assert reverse("feedback_detail", args=[feedback.pk]) in content


def test_a_ticket_without_reference_is_listed_with_a_placeholder(user, client):
    ticket = VendorTicketFactory(ref=None)
    content = client.get(reverse("vendor_ticket_list")).content.decode()
    assert f"Sans réf. (#{ticket.pk})" in content


def test_the_jira_link_is_shown_to_staff_only(client):
    VendorTicketFactory(ref="TEST-88")
    jira_url = "https://jira.example.com/browse/TEST-88"
    client.force_login(UserFactory())
    assert jira_url not in client.get(reverse("vendor_ticket_list")).content.decode()
    client.force_login(StaffFactory())
    assert jira_url in client.get(reverse("vendor_ticket_list")).content.decode()
