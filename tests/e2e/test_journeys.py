import pytest
from playwright.sync_api import expect

from tests.tracker.factories import FeedbackFactory, VendorTicketFactory
from tracker.choices import FeedbackType
from tracker.models import Feedback, VendorTicket
from tracker.statuses import CLOSED, RETEST_USER, SENT_TO_VENDOR

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


def test_author_answers_a_retest_ok(page, live_server, user, login):
    feedback = FeedbackFactory(author=user, status=RETEST_USER)
    login(page, user)
    page.goto(f"{live_server.url}/feedbacks/{feedback.pk}/")

    page.get_by_role("button", name="Test OK").click()

    expect(page.get_by_text("Retest demandé")).to_have_count(0)
    feedback.refresh_from_db()
    assert (feedback.status, feedback.closure_reason) == ("test_passed", "fixed")


def test_author_answers_a_retest_ko_comment_is_mandatory(page, live_server, user, login):
    feedback = FeedbackFactory(author=user, status=RETEST_USER)
    login(page, user)
    page.goto(f"{live_server.url}/feedbacks/{feedback.pk}/")

    # Without a comment the answer is refused server-side and nothing changes.
    with page.expect_navigation():
        page.get_by_role("button", name="Test KO").click()
    feedback.refresh_from_db()
    assert feedback.status == RETEST_USER
    expect(page.get_by_text("Retest demandé")).to_be_visible()

    page.fill("textarea[name='comment']", "Le montant est toujours faux")
    page.get_by_role("button", name="Test KO").click()

    expect(page.get_by_text("Retest demandé")).to_have_count(0)
    expect(page.get_by_text("Le montant est toujours faux").first).to_be_visible()
    feedback.refresh_from_db()
    assert feedback.status == "test_failed"


def test_staff_creates_a_vendor_ticket_from_a_feedback(page, live_server, staff, login):
    feedback = FeedbackFactory(page="Clients", tab="Adresses")
    login(page, staff)
    page.goto(f"{live_server.url}/feedbacks/{feedback.pk}/")

    page.get_by_role("link", name="Créer le ticket Aptean").click()
    # A click only waits for the navigation to start: wait for the scripts (CDN included) before typing.
    page.wait_for_load_state()
    page.fill("#id_ref", "TEST-321")
    # The link is rebuilt live from the reference (jira_link.js).
    expect(page.locator("#id_url")).to_have_value("https://jira.example.com/browse/TEST-321")
    page.get_by_role("button", name="Enregistrer").click()

    expect(page.get_by_text("Le ticket Monin passe en").first).to_be_visible()
    ticket = VendorTicket.objects.get()
    assert (ticket.ref, ticket.url) == ("TEST-321", "https://jira.example.com/browse/TEST-321")
    feedback.refresh_from_db()
    assert list(feedback.vendor_tickets.all()) == [ticket]
    assert feedback.status == SENT_TO_VENDOR


def test_user_switches_language_and_the_choice_sticks(page, live_server, user, login):
    login(page, user)
    page.goto(f"{live_server.url}/")
    expect(page.locator("html")).to_have_attribute("lang", "fr")
    expect(page.get_by_role("link", name="Tickets Aptean")).to_be_visible()

    page.get_by_role("button", name="EN", exact=True).click()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("link", name="Aptean tickets")).to_be_visible()

    # The choice is kept on the next pages (cookie).
    page.get_by_role("link", name="Aptean tickets").click()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("button", name="Log out")).to_be_visible()

    page.get_by_role("button", name="FR", exact=True).click()
    expect(page.locator("html")).to_have_attribute("lang", "fr")
    expect(page.get_by_role("button", name="Déconnexion")).to_be_visible()
