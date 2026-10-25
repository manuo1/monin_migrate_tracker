"""
All history writing lives here. `services.py` and views call these functions and NEVER write a history row
(FeedbackEvent, VendorTicketEvent, StatusChange) directly.

Two histories:
- feedback: StatusChange (statuses, the first row = creation) + FeedbackEvent (everything else);
  comments are real Comment rows (content), not history.
- vendor ticket: VendorTicketEvent.

Traced events (feedback): creation, status, closure reason, form fields, vendor links, attachments added / removed,
copy from another feedback. Traced events (vendor ticket): creation, fields, feedback links.

Deliberately not traced: attachments provided at creation (part of the creation) and everything done in the Django
admin (emergency tool, including ticket deletion).

Event texts are stored in the database and identical for everyone: ENGLISH ONLY, whatever the active language.
Lazy labels (type, closure reason, vendor status) are evaluated under `translation.override("en")` (see `_en`):
a stored f-string would otherwise be frozen in the writer's language.
"""

from django.utils import translation

from .choices import ClosureReason, FeedbackType
from .models import FeedbackEvent, StatusChange, VendorTicketEvent
from .statuses import VENDOR_STATUS_BY_CODE

# --- Raw writing (internal to this module) ---


def _event(feedback, author, text):
    FeedbackEvent.objects.create(feedback=feedback, author=author, text=text)


def _vendor_event(ticket, author, text):
    VendorTicketEvent.objects.create(ticket=ticket, author=author, text=text)


def _en(label):
    """English text of a lazy label, whatever the active language."""
    with translation.override("en"):
        return str(label)


def _ticket_label(ticket):
    """English label of a vendor ticket (the no-reference placeholder is translated), for stored texts."""
    with translation.override("en"):
        return ticket.label


def _shown(value):
    return value if value not in ("", None) else "(empty)"


# --- Feedback: form fields ---

# Feedback fields whose manual modification (form or admin) is traced, with their displayed name.
TRACKED_FIELDS = {
    "type": "Type",
    "page": "Page",
    "tab": "Tab",
    "article_id": "Tested article",
    "description": "Description",
}


def _shown_field(field, value):
    if field == "type":
        value = _en(dict(FeedbackType.choices).get(value, value))
    return _shown(value)


def diff_texts(before, after):
    """One line per traced field whose value differs between two versions of a feedback."""
    texts = []
    for field, label in TRACKED_FIELDS.items():
        old, new = getattr(before, field), getattr(after, field)
        if old != new:
            texts.append(f'{label} modified: "{_shown_field(field, old)}" → "{_shown_field(field, new)}"')
    return texts


def record_field_changes(before, after, author):
    """Trace the modified form fields. Returns the number of changes."""
    texts = diff_texts(before, after)
    for text in texts:
        _event(after, author, text)
    return len(texts)


# --- Feedback: status, closure reason ---


def record_status(feedback, author):
    """Add the current status to the status history (also called at creation: first row)."""
    StatusChange.objects.create(feedback=feedback, status=feedback.status, author=author)


def record_closure_reason(feedback, author, reason):
    if reason:
        _event(feedback, author, f"Closure reason: {_en(ClosureReason(reason).label)}")
    else:
        _event(feedback, author, "Closure reason removed")


# --- Feedback <-> vendor ticket links (one line on each side) ---


def record_links(feedback, before, after, author):
    """`before` and `after`: sets of linked vendor tickets. Returns True if something changed."""
    added = sorted(set(after) - set(before), key=_ticket_label)
    removed = sorted(set(before) - set(after), key=_ticket_label)
    for ticket in added:
        _event(feedback, author, f"Aptean ticket added: {_ticket_label(ticket)}")
        _vendor_event(ticket, author, f"Linked to Monin ticket #{feedback.pk}")
    for ticket in removed:
        _event(feedback, author, f"Aptean ticket removed: {_ticket_label(ticket)}")
        _vendor_event(ticket, author, f"Unlinked from Monin ticket #{feedback.pk}")
    return bool(added or removed)


# --- Attachments, copy ---


def record_attachments_added(feedback, author, names):
    _event(feedback, author, "Attachment(s) added: " + ", ".join(names))


def record_attachment_removed(feedback, author, name):
    _event(feedback, author, f"Attachment removed: {name}")


def record_copy(feedback, author, source, attachment_names=()):
    text = f"Ticket copied from ticket #{source.pk}"
    if attachment_names:
        text += " (attachments carried over: " + ", ".join(attachment_names) + ")"
    _event(feedback, author, text)


# --- Vendor ticket ---

VENDOR_TRACKED_FIELDS = {
    "ref": "Reference",
    "title": "Title",
    "description": "Description",
    "page": "Page",
    "tab": "Tab",
    "status": "Status",
    "url": "Link",
    "created_on": "Creation date",
}


def _shown_vendor_field(field, value):
    if field == "status":
        value = _en(VENDOR_STATUS_BY_CODE[value].label) if value in VENDOR_STATUS_BY_CODE else ""
    elif field == "created_on" and value:
        value = value.strftime("%Y-%m-%d")
    return _shown(value)


def vendor_diff_texts(before, after):
    """One line per field whose value differs between two versions of a vendor ticket."""
    texts = []
    for field, label in VENDOR_TRACKED_FIELDS.items():
        old, new = getattr(before, field), getattr(after, field)
        if old != new:
            texts.append(f'{label}: "{_shown_vendor_field(field, old)}" → "{_shown_vendor_field(field, new)}"')
    return texts


def record_vendor_field_changes(before, after, author):
    """Call after saving `after`: trace the modified fields. Returns the number of changes."""
    texts = vendor_diff_texts(before, after)
    for text in texts:
        _vendor_event(after, author, text)
    return len(texts)


def record_vendor_creation(ticket, author, feedback=None):
    text = "Aptean ticket created"
    if feedback is not None:
        text += f" from Monin ticket #{feedback.pk}"
    _vendor_event(ticket, author, text)
