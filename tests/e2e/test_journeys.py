import pytest
from playwright.sync_api import expect

from tests.tracker.factories import FeedbackFactory, VendorTicketFactory
from tracker.choices import FeedbackType
from tracker.models import Feedback
from tracker.statuses import CLOSED, SENT_TO_VENDOR

pytestmark = pytest.mark.e2e


def test_user_logs_in_and_creates_a_feedback(page, live_server, user, login, fill_reference):
    login(page, user)

    page.goto(f"{live_server.url}/feedbacks/new/")
    page.select_option("#id_type", FeedbackType.BUG)
    fill_reference(page, "id_page", "Clients")
    fill_reference(page, "id_tab", "Adresses")
    page.fill("#id_description", "Montant faux sur la facture")
    page.get_by_role("button", name="Enregistrer").click()

    expect(page.get_by_text("Montant faux sur la facture").first).to_be_visible()
    feedback = Feedback.objects.get()
    assert feedback.author == user
    assert (feedback.page, feedback.tab) == ("Clients", "Adresses")


def test_staff_triages_a_feedback_then_closes_it(page, live_server, staff, login):
    feedback = FeedbackFactory()
    ticket = VendorTicketFactory()
    login(page, staff)
    page.goto(f"{live_server.url}/feedbacks/{feedback.pk}/")
    triage = page.locator("form[action$='/triage/']")

    # Linking a vendor ticket to a new feedback transmits it (rule T1).
    triage.locator("#id_vendor_tickets").select_option(str(ticket.pk))
    triage.locator("#id_explanation").fill("Pris en compte par l'éditeur")
    triage.get_by_role("button", name="Enregistrer").click()

    expect(page.get_by_text("Pris en compte par l'éditeur").first).to_be_visible()
    feedback.refresh_from_db()
    assert feedback.status == SENT_TO_VENDOR
    assert list(feedback.vendor_tickets.all()) == [ticket]
    assert feedback.comments.get().author == staff

    # Closing with a reason.
    triage.locator("#id_status").select_option(CLOSED)
    triage.locator("#id_closure_reason").select_option("fixed")
    triage.locator("#id_explanation").fill("Corrigé dans la nouvelle version")
    triage.get_by_role("button", name="Enregistrer").click()

    expect(page.get_by_text("Corrigé dans la nouvelle version").first).to_be_visible()
    feedback.refresh_from_db()
    assert (feedback.status, feedback.closure_reason) == (CLOSED, "fixed")
