import pytest

from tests.tracker.factories import FeedbackFactory, VendorTicketFactory
from tracker.models import Attachment
from tracker.statuses import NEW, VENDOR_TO_TEST

pytestmark = pytest.mark.django_db


def test_vendor_ticket_label_is_its_reference():
    assert VendorTicketFactory(ref="TEST-42").label == "TEST-42"


def test_vendor_ticket_without_reference_gets_a_placeholder_label():
    ticket = VendorTicketFactory(ref=None)
    assert ticket.label == f"Sans réf. (#{ticket.pk})"


def test_several_vendor_tickets_without_reference_can_coexist():
    VendorTicketFactory(ref=None)
    VendorTicketFactory(ref=None)


def test_vendor_ticket_link_is_built_from_the_reference_and_the_configured_jira_url():
    assert VendorTicketFactory(ref="TEST-42").link == "https://jira.example.com/browse/TEST-42"


def test_vendor_ticket_stored_url_wins_over_the_built_one():
    assert VendorTicketFactory(ref="TEST-42", url="https://example.com/x").link == "https://example.com/x"


def test_vendor_ticket_without_reference_nor_url_has_no_link():
    assert VendorTicketFactory(ref=None).link == ""


def test_vendor_ticket_status_info():
    assert VendorTicketFactory(status=VENDOR_TO_TEST).status_info.label == "À tester"
    assert VendorTicketFactory(status="").status_info is None


def test_feedback_defaults_to_new_and_exposes_its_status_definition():
    feedback = FeedbackFactory()
    assert feedback.status == NEW
    assert feedback.status_info.label == "Nouveau"


@pytest.mark.parametrize(
    ("filename", "kind"),
    [("a.PNG", "image"), ("a.mp4", "video"), ("a.pdf", "pdf"), ("a.docx", "other"), ("noextension", "other")],
)
def test_attachment_kind(filename, kind):
    attachment = Attachment(feedback=FeedbackFactory(), file=f"feedbacks/2026/10/{filename}")
    assert attachment.kind == kind
    assert attachment.name == filename
