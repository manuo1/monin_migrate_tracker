import pytest
from django.utils import translation

from tracker import history
from tracker.models import Page, Tab, VendorTicketEvent

from .factories import FeedbackFactory, StaffFactory, VendorTicketFactory

pytestmark = pytest.mark.django_db


def test_reference_models_verbose_names_follow_the_active_language():
    assert str(Page._meta.verbose_name) == "page"
    assert str(Page._meta.verbose_name_plural) == "pages"
    assert str(Tab._meta.verbose_name) == "onglet"
    assert str(Tab._meta.verbose_name_plural) == "onglets"
    with translation.override("en"):
        assert str(Tab._meta.verbose_name) == "tab"
        assert str(Tab._meta.verbose_name_plural) == "tabs"


def test_vendor_ticket_label_without_ref_follows_the_active_language():
    ticket = VendorTicketFactory(ref=None)
    assert ticket.label == f"Sans réf. (#{ticket.pk})"
    with translation.override("en"):
        assert ticket.label == f"No ref. (#{ticket.pk})"


def test_vendor_ticket_label_with_ref_is_the_ref():
    ticket = VendorTicketFactory(ref="TEST-1")
    with translation.override("en"):
        assert ticket.label == "TEST-1"


def test_stored_link_events_use_the_english_label_whatever_the_writer_language():
    staff = StaffFactory()
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory(ref=None)
    with translation.override("fr"):
        history.record_links(feedback, set(), {ticket}, staff)
    assert feedback.events.get().text == f"Aptean ticket added: No ref. (#{ticket.pk})"
    assert VendorTicketEvent.objects.get().text == f"Linked to Monin ticket #{feedback.pk}"
