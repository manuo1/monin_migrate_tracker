"""Writes to the database (statuses, links, attachments). Business rules live in `rules.py` (which decides without
writing) and are applied here: T1 (transmission to the vendor when a vendor ticket is added) and T2 (answer to the
user's retest). Everything else is free and manual: a status is changed by hand without validation.
Every history row goes through `history.py`: this module never writes an event itself.
"""

import hashlib

from django.core.exceptions import PermissionDenied
from django.db import transaction

from . import history, rules
from .models import Comment, Feedback, VendorTicket


class StaleStateError(Exception):
    """The feedback changed (status, closure reason or vendor links) since the triage form was displayed."""


# --- Feedbacks ---


def create_feedback(*, author, files=None, source=None, copied_attachment_ids=(), **fields):
    """
    Create a feedback (status "new"), its first history row and its attachments.
    If `source` is given (copy of another feedback): reuse the attachments whose id is in `copied_attachment_ids`
    (same file on disk, no duplication) and trace the copy.
    """
    with transaction.atomic():
        feedback = Feedback.objects.create(author=author, **fields)
        history.record_status(feedback, author)
        for file in files or []:
            feedback.attachments.create(file=file)
        if source is not None:
            ids = [i for i in copied_attachment_ids if str(i).isdigit()]
            names = [feedback.attachments.create(file=a.file.name).name for a in source.attachments.filter(pk__in=ids)]
            history.record_copy(feedback, author, source, names)
    return feedback


def save_changes(before, after, author):
    """Save `after` and trace each field modified compared to `before`. Returns the number of changes."""
    with transaction.atomic():
        after.save()
        return history.record_field_changes(before, after, author)


def add_attachments(feedback, files, author):
    with transaction.atomic():
        names = [feedback.attachments.create(file=f).name for f in files]
        history.record_attachments_added(feedback, author, names)


def remove_attachment(feedback, attachment, author):
    """Detach the file from the feedback (database link) and trace it; the file stays on disk."""
    with transaction.atomic():
        history.record_attachment_removed(feedback, author, attachment.name)
        attachment.delete()


def add_comment(feedback, author, text):
    """Add a comment to a feedback (open to every logged-in user). Returns the comment."""
    return Comment.objects.create(feedback=feedback, author=author, text=text.strip())


def change_status(feedback, status, author, closure_reason="", explanation=""):
    """Entry point to change a feedback status: history, closure reason, optional comment. No validation rule."""
    with transaction.atomic():
        if feedback.status != status:
            feedback.status = status
            history.record_status(feedback, author)
        if closure_reason != feedback.closure_reason:
            history.record_closure_reason(feedback, author, closure_reason)
        feedback.closure_reason = closure_reason
        feedback.save()
        if explanation.strip():
            Comment.objects.create(feedback=feedback, author=author, text=explanation.strip())


def triage_state(feedback):
    """Short fingerprint of what the triage form edits (status, closure reason, vendor links), read from the database"""
    tickets = sorted(feedback.vendor_tickets.values_list("pk", flat=True))
    raw = f"{feedback.status}|{feedback.closure_reason}|{tickets}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def triage(feedback, author, *, status, closure_reason, explanation, vendor_tickets, expected_state=None):
    """
    Full update from the triage form, with a trace of each change.
    Optimistic locking: if `expected_state` (the `triage_state` shown with the form) no longer matches the database,
    nothing is written and StaleStateError is raised. The row is locked (PostgreSQL) while the check and the write run.
    """
    with transaction.atomic():
        if expected_state is not None:
            current = Feedback.objects.select_for_update().get(pk=feedback.pk)
            if triage_state(current) != expected_state:
                raise StaleStateError
        change_status(feedback, status, author, closure_reason=closure_reason, explanation=explanation)
        update_vendor_links(feedback, vendor_tickets, author)


# --- User retest ---


def answer_retest(feedback, author, answer, comment=""):
    """
    Rule T2: answer to the user's retest ("ok" -> test passed, reason "fixed"; "ko" -> test failed, comment required).
    PermissionDenied if `author` cannot answer; ValueError if the answer is unknown or the comment is missing.
    Returns the new status code.
    """
    if not rules.retest_is_open(feedback, author):
        raise PermissionDenied("Ce ticket n'est pas en attente de retest pour vous.")
    status, closure_reason = rules.retest_outcome(answer)
    comment = (comment or "").strip()
    if rules.comment_required(answer) and not comment:
        raise ValueError("Un commentaire est obligatoire pour un Test KO : expliquez ce qui ne va pas.")
    change_status(feedback, status, author, closure_reason=closure_reason, explanation=comment)
    return status


# --- Feedback <-> vendor ticket links ---


def update_vendor_links(feedback, tickets, author):
    """
    Replace the vendor tickets linked to the feedback by `tickets`. Returns True if something changed.
    Rule T1 (rules.py): if a vendor ticket is added, the feedback may change status ("new" -> "sent to vendor").
    """
    current = set(feedback.vendor_tickets.all())
    new = set(tickets)
    if current == new:
        return False
    with transaction.atomic():
        feedback.vendor_tickets.set(new)
        history.record_links(feedback, current, new, author)
        if new - current:
            status = rules.status_after_vendor_link(feedback)
            if status:
                change_status(feedback, status, author, closure_reason=feedback.closure_reason)
    return True


def link_vendor_ticket(feedback, ticket, author):
    """Add `ticket` to the feedback's vendor tickets (traced on both sides), leaving the other links untouched."""
    update_vendor_links(feedback, set(feedback.vendor_tickets.all()) | {ticket}, author)


def associate_vendor_tickets(feedback, tickets, author):
    """Add vendor tickets to the existing links (nothing is removed). Returns True if a link was added."""
    return update_vendor_links(feedback, set(feedback.vendor_tickets.all()) | set(tickets), author)


# --- Vendor tickets ---


def create_vendor_ticket(*, author, source=None, **fields):
    """Create the vendor ticket, trace its creation and, if `source` (a feedback) is given, link it."""
    with transaction.atomic():
        ticket = VendorTicket.objects.create(**fields)
        history.record_vendor_creation(ticket, author, feedback=source)
        if source is not None:
            link_vendor_ticket(source, ticket, author)
    return ticket


def save_vendor_ticket(before, after, author):
    """Save `after` and trace each field modified compared to `before`. Returns the number of changes."""
    with transaction.atomic():
        after.save()
        return history.record_vendor_field_changes(before, after, author)


def build_vendor_description(feedback):
    """
    Vendor ticket description (Jira format: steps then finding) built from a feedback.
    The headings are always present, even when the feedback lacks the information (empty article or tab).
    """
    return (
        "Se rendre:\n"
        f"{feedback.page}\n"
        "choisir\n"
        f"{feedback.article_id}\n"
        "chapitre\n"
        f"{feedback.tab}\n"
        "\n"
        "constater que\n"
        f"{feedback.description}"
    )
