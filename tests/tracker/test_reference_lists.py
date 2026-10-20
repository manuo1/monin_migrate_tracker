import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker.models import Page, Tab

pytestmark = pytest.mark.django_db

SCRIPT = "tracker/reference_lists.js"


def _urls():
    return {
        "feedback_create": reverse("feedback_create"),
        "feedback_edit": reverse("feedback_edit", args=[FeedbackFactory().pk]),
        "vendor_ticket_create": reverse("vendor_ticket_create"),
        "vendor_ticket_edit": reverse("vendor_ticket_edit", args=[VendorTicketFactory().pk]),
    }


PAGES = ["feedback_create", "feedback_edit", "vendor_ticket_create", "vendor_ticket_edit"]


@pytest.mark.parametrize("page", PAGES)
def test_forms_offer_the_reference_lists_on_page_and_tab_inputs(client, page):
    Page.objects.create(name="Articles")
    Tab.objects.create(name="Adresses")
    client.force_login(StaffFactory())

    content = client.get(_urls()[page]).content.decode()

    assert '<datalist id="reference-pages"><option value="Articles"></datalist>' in content
    assert '<datalist id="reference-tabs"><option value="Adresses"></datalist>' in content
    assert 'list="reference-pages"' in content
    assert 'list="reference-tabs"' in content
    assert SCRIPT in content


def test_reference_values_are_escaped(client):
    Page.objects.create(name='A&B "quoted"')
    client.force_login(UserFactory())
    content = client.get(reverse("feedback_create")).content.decode()
    assert 'value="A&amp;B &quot;quoted&quot;"' in content


def test_context_processor_exposes_both_lists_sorted_by_name(client):
    Page.objects.create(name="Clients")
    Page.objects.create(name="Articles")
    Tab.objects.create(name="Adresses")
    client.force_login(UserFactory())

    response = client.get(reverse("feedback_create"))

    assert list(response.context["ref_pages"]) == ["Articles", "Clients"]
    assert list(response.context["ref_tabs"]) == ["Adresses"]


def test_staff_flag_drives_the_out_of_list_highlight(client):
    client.force_login(UserFactory())
    assert 'data-staff="false"' in client.get(reverse("feedback_create")).content.decode()

    client.force_login(StaffFactory())
    assert 'data-staff="true"' in client.get(reverse("feedback_create")).content.decode()


def test_pages_without_the_inputs_do_not_query_the_lists(client):
    # Lazy lists: the feedback list page never renders them, so no query is made for them.
    client.force_login(UserFactory())
    with CaptureQueriesContext(connection) as queries:
        client.get(reverse("feedback_list"))
    assert not [q for q in queries if "tracker_page" in q["sql"] or "tracker_tab" in q["sql"]]
