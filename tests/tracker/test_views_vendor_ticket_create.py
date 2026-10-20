import pytest
from django.urls import reverse
from django.utils import timezone

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker import services
from tracker.models import VendorTicket
from tracker.statuses import NEW, SENT_TO_VENDOR, VENDOR_IN_PROGRESS

pytestmark = pytest.mark.django_db

CREATE_URL = "vendor_ticket_create"


def _url(feedback=None):
    url = reverse(CREATE_URL)
    return f"{url}?feedback={feedback.pk}" if feedback else url


def _data(**overrides):
    data = {
        "ref": "TEST-321",
        "title": "Clients Adresses",
        "description": "Description Jira",
        "page": "Clients",
        "tab": "Adresses",
        "status": VENDOR_IN_PROGRESS,
        "url": "",
        "created_on": "2026-03-14",
    }
    data.update(overrides)
    return data


# --- Permission matrix: anonymous / user / staff ---


def test_anonymous_is_redirected_to_login(client):
    for response in (client.get(_url()), client.post(_url(), _data())):
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    assert not VendorTicket.objects.exists()


def test_non_staff_cannot_create(client):
    client.force_login(UserFactory())
    assert client.get(_url()).status_code == 403
    assert client.post(_url(), _data()).status_code == 403
    assert not VendorTicket.objects.exists()


def test_staff_sees_the_form(client):
    client.force_login(StaffFactory())
    assert client.get(_url()).status_code == 200


# --- Prefilled form ---


def test_form_is_prefilled_from_the_feedback(client):
    client.force_login(StaffFactory())
    feedback = FeedbackFactory(page="Clients", tab="Adresses", description="Le champ est vide")

    response = client.get(_url(feedback))

    initial = response.context["form"].initial
    assert initial["ref"] == "TEST-"
    assert initial["page"] == "Clients"
    assert initial["tab"] == "Adresses"
    assert initial["title"] == "Clients Adresses"
    assert initial["description"] == services.build_vendor_description(feedback)
    assert initial["status"] == VENDOR_IN_PROGRESS
    assert initial["created_on"] == timezone.localdate()
    assert response.context["source"] == feedback
    assert response.context["form"].fields["ref"].required is True


def test_title_of_a_feedback_without_tab_has_no_trailing_space(client):
    client.force_login(StaffFactory())
    feedback = FeedbackFactory(page="Clients", tab="")
    assert client.get(_url(feedback)).context["form"].initial["title"] == "Clients"


def test_form_without_feedback_only_prefills_the_reference_prefix(client):
    client.force_login(StaffFactory())
    response = client.get(_url())
    form = response.context["form"]
    assert form.initial == {"ref": "TEST-"}
    assert form.fields["ref"].required is False
    assert response.context["source"] is None


@pytest.mark.parametrize("param", ["abc", "999999", ""])
def test_unknown_feedback_parameter_is_ignored(client, param):
    client.force_login(StaffFactory())
    response = client.get(reverse(CREATE_URL), {"feedback": param})
    assert response.status_code == 200
    assert response.context["source"] is None


def test_the_jira_creation_form_link_is_offered(client):
    client.force_login(StaffFactory())
    assert "https://jira.example.com/form/00000000" in client.get(_url(FeedbackFactory())).content.decode()


# --- Creation from a feedback ---


def test_creation_from_a_feedback_creates_links_and_traces(client):
    staff = StaffFactory()
    client.force_login(staff)
    feedback = FeedbackFactory(status=NEW)

    response = client.post(_url(feedback), _data(), follow=True)

    ticket = VendorTicket.objects.get()
    assert response.redirect_chain == [(reverse("vendor_ticket_detail", args=[ticket.pk]), 302)]
    assert ticket.ref == "TEST-321"
    assert ticket.url == "https://jira.example.com/browse/TEST-321"
    assert ticket.status == VENDOR_IN_PROGRESS
    assert ticket.events.exists()
    feedback.refresh_from_db()
    assert list(feedback.vendor_tickets.all()) == [ticket]
    assert feedback.status == SENT_TO_VENDOR  # rule T1
    content = response.content.decode()
    assert f"lié au ticket Monin #{feedback.pk}" in content
    assert "Le ticket Monin passe en « Transmis Aptean »." in content


def test_reference_is_mandatory_when_created_from_a_feedback(client):
    client.force_login(StaffFactory())
    feedback = FeedbackFactory()
    response = client.post(_url(feedback), _data(ref=""))
    assert response.status_code == 200
    assert response.context["form"].errors["ref"]
    assert not VendorTicket.objects.exists()
    assert not feedback.vendor_tickets.exists()


def test_the_bare_prefix_is_refused_when_created_from_a_feedback(client):
    client.force_login(StaffFactory())
    feedback = FeedbackFactory()
    response = client.post(_url(feedback), _data(ref="TEST-"))
    assert response.status_code == 200
    assert "Indiquez le numéro du ticket après « TEST- »." in response.context["form"].errors["ref"]
    assert not VendorTicket.objects.exists()


def test_reference_already_used_is_refused(client):
    VendorTicketFactory(ref="TEST-321")
    client.force_login(StaffFactory())
    feedback = FeedbackFactory()
    response = client.post(_url(feedback), _data())
    assert response.status_code == 200
    assert response.context["form"].errors["ref"]
    assert VendorTicket.objects.count() == 1
    assert not feedback.vendor_tickets.exists()


# --- Creation without a feedback ---


def test_creation_without_feedback_may_have_no_reference_and_is_not_linked(client):
    client.force_login(StaffFactory())

    response = client.post(_url(), _data(ref="", url="https://jira.example.com/browse/CUSTOM-1"))

    ticket = VendorTicket.objects.get()
    assert response.url == reverse("vendor_ticket_detail", args=[ticket.pk])
    assert ticket.ref is None
    assert ticket.url == "https://jira.example.com/browse/CUSTOM-1"
    assert not ticket.feedbacks.exists()
    assert ticket.events.exists()


def test_bare_prefix_means_no_reference_without_feedback(client):
    client.force_login(StaffFactory())
    client.post(_url(), _data(ref="TEST-"))
    assert VendorTicket.objects.get().ref is None


# --- Entry points ---


def test_feedback_detail_offers_the_creation_to_staff_only(client):
    feedback = FeedbackFactory()
    detail = reverse("feedback_detail", args=[feedback.pk])
    link = _url(feedback)

    client.force_login(feedback.author)
    assert reverse(CREATE_URL) not in client.get(detail).content.decode()

    client.force_login(StaffFactory())
    assert link in client.get(detail).content.decode()


def test_vendor_ticket_list_offers_the_creation_to_staff_only(client):
    client.force_login(UserFactory())
    assert reverse(CREATE_URL) not in client.get(reverse("vendor_ticket_list")).content.decode()

    client.force_login(StaffFactory())
    assert reverse(CREATE_URL) in client.get(reverse("vendor_ticket_list")).content.decode()
