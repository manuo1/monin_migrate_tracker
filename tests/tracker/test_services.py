import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import translation

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker import services
from tracker.choices import ClosureReason, FeedbackType
from tracker.models import Feedback, VendorTicket
from tracker.statuses import (
    CLOSED,
    IN_ANALYSIS,
    NEW,
    RETEST_USER,
    SENT_TO_VENDOR,
    TEST_FAILED,
    TEST_PASSED,
    VENDOR_TO_TEST,
)

pytestmark = pytest.mark.django_db


def upload(name="shot.png"):
    return SimpleUploadedFile(name, b"content")


def status_history(feedback):
    return [row.status for row in feedback.status_history.all()]


def event_texts(obj):
    return [event.text for event in obj.events.all()]


# --- stored event texts are English whatever the writer's language ---


def test_stored_events_are_english_when_the_writer_uses_french():
    feedback = FeedbackFactory(status=NEW, type=FeedbackType.BUG)
    ticket = VendorTicketFactory(status="")
    before_feedback = Feedback.objects.get(pk=feedback.pk)
    before_ticket = VendorTicket.objects.get(pk=ticket.pk)
    staff = StaffFactory()
    with translation.override("fr"):
        feedback.type = FeedbackType.SUGGESTION
        services.save_changes(before_feedback, feedback, staff)
        services.change_status(feedback, CLOSED, staff, closure_reason=ClosureReason.REJECTED)
        ticket.status = VENDOR_TO_TEST
        services.save_vendor_ticket(before_ticket, ticket, staff)
    assert event_texts(feedback) == ['Type modified: "Bug" → "Suggestion"', "Closure reason: Rejected"]
    assert event_texts(ticket) == ['Status: "(empty)" → "To test"']


# --- create_feedback ---


def test_create_feedback_starts_new_with_its_first_status_row():
    author = UserFactory()
    feedback = services.create_feedback(author=author, type=FeedbackType.BUG, page="Articles", description="Boom")
    assert feedback.status == NEW
    assert feedback.author == author
    assert status_history(feedback) == [NEW]


def test_create_feedback_stores_files_without_tracing_them():
    feedback = services.create_feedback(
        author=UserFactory(), type=FeedbackType.BUG, page="Articles", description="Boom", files=[upload()]
    )
    assert [a.name for a in feedback.attachments.all()] == ["shot.png"]
    assert event_texts(feedback) == []


def test_create_feedback_from_a_source_reuses_files_and_traces_the_copy():
    source = FeedbackFactory()
    attachment = source.attachments.create(file=upload("a.png"))
    other = source.attachments.create(file=upload("b.png"))
    copy = services.create_feedback(
        author=UserFactory(),
        type=FeedbackType.BUG,
        page="Articles",
        description="Again",
        source=source,
        copied_attachment_ids=[str(attachment.pk), "not-a-number"],
    )
    assert [a.file.name for a in copy.attachments.all()] == [attachment.file.name]
    assert other.file.name not in [a.file.name for a in copy.attachments.all()]
    assert event_texts(copy) == [f"Ticket copied from ticket #{source.pk} (attachments carried over: a.png)"]


# --- save_changes ---


def test_save_changes_traces_modified_fields_and_returns_their_count():
    feedback = FeedbackFactory(page="Articles")
    before = Feedback.objects.get(pk=feedback.pk)
    feedback.page = "Clients"
    assert services.save_changes(before, feedback, StaffFactory()) == 1
    assert event_texts(feedback) == ['Page modified: "Articles" → "Clients"']
    assert Feedback.objects.get(pk=feedback.pk).page == "Clients"


def test_save_changes_without_modification_traces_nothing():
    feedback = FeedbackFactory()
    before = Feedback.objects.get(pk=feedback.pk)
    assert services.save_changes(before, feedback, StaffFactory()) == 0
    assert event_texts(feedback) == []


# --- attachments ---


def test_add_attachments_traces_all_names():
    feedback = FeedbackFactory()
    services.add_attachments(feedback, [upload("a.png"), upload("b.png")], StaffFactory())
    assert event_texts(feedback) == ["Attachment(s) added: a.png, b.png"]


def test_remove_attachment_unlinks_it_but_keeps_the_file_on_disk():
    feedback = FeedbackFactory()
    attachment = feedback.attachments.create(file=upload("a.png"))
    stored_name = attachment.file.name
    services.remove_attachment(feedback, attachment, StaffFactory())
    assert feedback.attachments.count() == 0
    assert default_storage.exists(stored_name)
    assert event_texts(feedback) == ["Attachment removed: a.png"]


def test_removing_a_copied_attachment_keeps_the_file_for_the_other_feedback():
    source = FeedbackFactory()
    source.attachments.create(file=upload("a.png"))
    copy = services.create_feedback(
        author=UserFactory(),
        type=FeedbackType.BUG,
        page="Articles",
        description="Copy",
        source=source,
        copied_attachment_ids=[str(source.attachments.get().pk)],
    )
    services.remove_attachment(copy, copy.attachments.get(), StaffFactory())
    assert default_storage.exists(source.attachments.get().file.name)


# --- change_status ---


def test_change_status_records_a_status_row_once():
    feedback = FeedbackFactory()
    staff = StaffFactory()
    services.change_status(feedback, IN_ANALYSIS, staff)
    services.change_status(feedback, IN_ANALYSIS, staff)
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS
    assert status_history(feedback) == [IN_ANALYSIS]


def test_change_status_traces_the_closure_reason_and_turns_the_explanation_into_a_comment():
    feedback = FeedbackFactory()
    services.change_status(
        feedback, CLOSED, StaffFactory(), closure_reason=ClosureReason.REJECTED, explanation="  Out of scope \n"
    )
    feedback.refresh_from_db()
    assert feedback.closure_reason == ClosureReason.REJECTED
    assert event_texts(feedback) == ["Closure reason: Rejected"]
    assert [c.text for c in feedback.comments.all()] == ["Out of scope"]


def test_change_status_traces_the_removal_of_a_closure_reason():
    feedback = FeedbackFactory(status=CLOSED, closure_reason=ClosureReason.FIXED)
    services.change_status(feedback, IN_ANALYSIS, StaffFactory(), closure_reason="")
    assert event_texts(feedback) == ["Closure reason removed"]


def test_change_status_without_explanation_adds_no_comment():
    feedback = FeedbackFactory()
    services.change_status(feedback, IN_ANALYSIS, StaffFactory(), explanation="   ")
    assert feedback.comments.count() == 0


# --- answer_retest (T2) ---


def test_answer_retest_ok_by_the_author_passes_the_test_and_closes_as_fixed():
    author = UserFactory()
    feedback = FeedbackFactory(status=RETEST_USER, author=author)
    assert services.answer_retest(feedback, author, "ok") == TEST_PASSED
    feedback.refresh_from_db()
    assert (feedback.status, feedback.closure_reason) == (TEST_PASSED, ClosureReason.FIXED)
    assert status_history(feedback) == [TEST_PASSED]


def test_answer_retest_ko_requires_a_comment():
    author = UserFactory()
    feedback = FeedbackFactory(status=RETEST_USER, author=author)
    with pytest.raises(ValueError, match="commentaire est obligatoire"):
        services.answer_retest(feedback, author, "ko", comment="   ")
    feedback.refresh_from_db()
    assert feedback.status == RETEST_USER


def test_answer_retest_ko_with_a_comment_fails_the_test_and_keeps_the_comment():
    author = UserFactory()
    feedback = FeedbackFactory(status=RETEST_USER, author=author)
    assert services.answer_retest(feedback, author, "ko", comment="Still broken") == TEST_FAILED
    assert [c.text for c in feedback.comments.all()] == ["Still broken"]


def test_answer_retest_is_allowed_to_staff_who_are_not_the_author():
    feedback = FeedbackFactory(status=RETEST_USER)
    assert services.answer_retest(feedback, StaffFactory(), "ok") == TEST_PASSED


def test_answer_retest_is_refused_to_another_user():
    feedback = FeedbackFactory(status=RETEST_USER)
    with pytest.raises(PermissionDenied):
        services.answer_retest(feedback, UserFactory(), "ok")


def test_answer_retest_is_refused_when_no_retest_is_requested():
    author = UserFactory()
    feedback = FeedbackFactory(status=NEW, author=author)
    with pytest.raises(PermissionDenied):
        services.answer_retest(feedback, author, "ok")


def test_answer_retest_rejects_an_unknown_answer():
    author = UserFactory()
    feedback = FeedbackFactory(status=RETEST_USER, author=author)
    with pytest.raises(ValueError, match="Unknown retest answer"):
        services.answer_retest(feedback, author, "maybe")


# --- vendor links (T1) ---


def test_adding_a_vendor_ticket_to_a_new_feedback_sends_it_to_the_vendor():
    feedback, ticket, staff = FeedbackFactory(), VendorTicketFactory(), StaffFactory()
    assert services.update_vendor_links(feedback, [ticket], staff) is True
    feedback.refresh_from_db()
    assert feedback.status == SENT_TO_VENDOR
    assert status_history(feedback) == [SENT_TO_VENDOR]
    assert event_texts(feedback) == [f"Aptean ticket added: {ticket.ref}"]
    assert event_texts(ticket) == [f"Linked to Monin ticket #{feedback.pk}"]


def test_adding_a_vendor_ticket_does_not_change_a_feedback_that_is_not_new():
    feedback = FeedbackFactory(status=IN_ANALYSIS)
    services.update_vendor_links(feedback, [VendorTicketFactory()], StaffFactory())
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS


def test_t1_keeps_the_closure_reason():
    feedback = FeedbackFactory(closure_reason=ClosureReason.NOT_REPRODUCED)
    services.update_vendor_links(feedback, [VendorTicketFactory()], StaffFactory())
    feedback.refresh_from_db()
    assert feedback.closure_reason == ClosureReason.NOT_REPRODUCED


def test_update_vendor_links_returns_false_and_traces_nothing_when_unchanged():
    ticket = VendorTicketFactory()
    feedback = FeedbackFactory(status=IN_ANALYSIS)
    feedback.vendor_tickets.add(ticket)
    assert services.update_vendor_links(feedback, [ticket], StaffFactory()) is False
    assert event_texts(feedback) == []


def test_removing_a_vendor_ticket_is_traced_on_both_sides_and_keeps_the_status():
    ticket = VendorTicketFactory()
    feedback = FeedbackFactory(status=SENT_TO_VENDOR)
    feedback.vendor_tickets.add(ticket)
    assert services.update_vendor_links(feedback, [], StaffFactory()) is True
    feedback.refresh_from_db()
    assert feedback.status == SENT_TO_VENDOR
    assert event_texts(feedback) == [f"Aptean ticket removed: {ticket.ref}"]
    assert event_texts(ticket) == [f"Unlinked from Monin ticket #{feedback.pk}"]


def test_link_vendor_ticket_keeps_the_existing_links():
    first, second = VendorTicketFactory(), VendorTicketFactory()
    feedback = FeedbackFactory(status=IN_ANALYSIS)
    feedback.vendor_tickets.add(first)
    services.link_vendor_ticket(feedback, second, StaffFactory())
    assert set(feedback.vendor_tickets.all()) == {first, second}


def test_associate_vendor_tickets_adds_without_removing():
    first, second = VendorTicketFactory(), VendorTicketFactory()
    feedback = FeedbackFactory(status=IN_ANALYSIS)
    feedback.vendor_tickets.add(first)
    assert services.associate_vendor_tickets(feedback, [second], StaffFactory()) is True
    assert services.associate_vendor_tickets(feedback, [first], StaffFactory()) is False
    assert set(feedback.vendor_tickets.all()) == {first, second}


# --- triage ---


def test_triage_updates_status_reason_comment_and_links_in_one_go():
    feedback, ticket = FeedbackFactory(), VendorTicketFactory()
    services.triage(
        feedback,
        StaffFactory(),
        status=NEW,
        closure_reason="",
        explanation="Sent to the vendor",
        vendor_tickets=[ticket],
    )
    feedback.refresh_from_db()
    assert feedback.status == SENT_TO_VENDOR
    assert [c.text for c in feedback.comments.all()] == ["Sent to the vendor"]
    assert list(feedback.vendor_tickets.all()) == [ticket]


def test_triage_respects_a_status_explicitly_chosen_by_staff_when_linking():
    feedback = FeedbackFactory()
    services.triage(
        feedback,
        StaffFactory(),
        status=IN_ANALYSIS,
        closure_reason="",
        explanation="",
        vendor_tickets=[VendorTicketFactory()],
    )
    feedback.refresh_from_db()
    assert feedback.status == IN_ANALYSIS


# --- vendor tickets ---


def test_create_vendor_ticket_from_a_feedback_traces_creation_links_and_transmits():
    feedback, staff = FeedbackFactory(), StaffFactory()
    ticket = services.create_vendor_ticket(author=staff, source=feedback, ref="TEST-900", title="T", page="Articles")
    feedback.refresh_from_db()
    assert feedback.status == SENT_TO_VENDOR
    assert list(feedback.vendor_tickets.all()) == [ticket]
    assert event_texts(ticket) == [
        f"Aptean ticket created from Monin ticket #{feedback.pk}",
        f"Linked to Monin ticket #{feedback.pk}",
    ]


def test_create_vendor_ticket_without_a_feedback_is_only_traced_as_created():
    ticket = services.create_vendor_ticket(author=StaffFactory(), ref="TEST-901", title="T")
    assert event_texts(ticket) == ["Aptean ticket created"]


def test_save_vendor_ticket_traces_modified_fields_and_returns_their_count():
    ticket = VendorTicketFactory(title="Old", status="")
    before = VendorTicket.objects.get(pk=ticket.pk)
    ticket.title = "New"
    ticket.status = VENDOR_TO_TEST
    assert services.save_vendor_ticket(before, ticket, StaffFactory()) == 2
    assert event_texts(ticket) == ['Title: "Old" → "New"', 'Status: "(empty)" → "To test"']


def test_vendor_description_follows_the_jira_format_and_keeps_empty_headings():
    feedback = FeedbackFactory(page="Articles", tab="Prix", article_id="A12", description="Le prix est faux")
    assert services.build_vendor_description(feedback) == (
        "Se rendre:\nArticles\nchoisir\nA12\nchapitre\nPrix\n\nconstater que\nLe prix est faux"
    )


def test_vendor_description_with_missing_information_keeps_all_headings():
    feedback = FeedbackFactory(page="Articles", tab="", article_id="", description="Boom")
    assert services.build_vendor_description(feedback) == (
        "Se rendre:\nArticles\nchoisir\n\nchapitre\n\n\nconstater que\nBoom"
    )
