"""Status definitions for feedbacks and vendor tickets.

Statuses live in code, not in database tables. They feed the `choices` of the model fields.
Adding, renaming or removing a status changes those `choices`: run `makemigrations` (no schema change).
If the code of an existing status changes, a data migration is also needed; a new color or label needs none.

This module only holds definitions. State-change rules live in `rules.py`.
Labels are English msgids (`gettext_lazy`), translated in `locale/<lang>/LC_MESSAGES/django.po`.
"""

from dataclasses import dataclass
from enum import StrEnum

from django.utils.translation import gettext_lazy as _


class StatusCategory(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass(frozen=True)
class FeedbackStatus:
    code: str
    label: str
    color: str  # Bootstrap color suffix: primary, success, warning...
    category: StatusCategory

    @property
    def is_final(self) -> bool:
        return self.category is StatusCategory.DONE


@dataclass(frozen=True)
class VendorStatus:
    code: str
    label: str
    color: str


# Feedback status codes used by the business rules.
NEW = "new"
IN_ANALYSIS = "in_analysis"
TO_REPLAY_WITH_USER = "to_replay_with_user"
SENT_TO_VENDOR = "sent_to_vendor"
RETEST_STAFF = "retest_staff"
RETEST_USER = "retest_user"
TEST_FAILED = "test_failed"
TEST_PASSED = "test_passed"
CLOSED = "closed"

# The order of this list is the display and sort order.
FEEDBACK_STATUSES = [
    FeedbackStatus(NEW, _("New"), "secondary", StatusCategory.TODO),
    FeedbackStatus(IN_ANALYSIS, _("In analysis"), "primary", StatusCategory.IN_PROGRESS),
    FeedbackStatus(TO_REPLAY_WITH_USER, _("To replay with the user"), "warning", StatusCategory.IN_PROGRESS),
    FeedbackStatus(SENT_TO_VENDOR, _("Sent to Aptean"), "info", StatusCategory.IN_PROGRESS),
    FeedbackStatus(RETEST_STAFF, _("To retest (staff)"), "warning", StatusCategory.IN_PROGRESS),
    FeedbackStatus(RETEST_USER, _("To retest (user)"), "primary", StatusCategory.IN_PROGRESS),
    FeedbackStatus(TEST_FAILED, _("Test failed"), "danger", StatusCategory.IN_PROGRESS),
    FeedbackStatus(TEST_PASSED, _("Test passed"), "success", StatusCategory.DONE),
    FeedbackStatus(CLOSED, _("Closed"), "success", StatusCategory.DONE),
]

# Vendor ticket status codes (the status is optional on a vendor ticket: empty string when unknown).
VENDOR_IN_PROGRESS = "in_progress"
VENDOR_TO_TEST = "to_test"
VENDOR_CLOSED = "closed"
VENDOR_BLOCKED = "blocked"

VENDOR_STATUSES = [
    VendorStatus(VENDOR_IN_PROGRESS, _("In progress"), "primary"),
    VendorStatus(VENDOR_TO_TEST, _("To test"), "warning"),
    VendorStatus(VENDOR_CLOSED, _("Closed"), "success"),
    VendorStatus(VENDOR_BLOCKED, _("Blocked"), "danger"),
]

FEEDBACK_STATUS_BY_CODE = {s.code: s for s in FEEDBACK_STATUSES}
VENDOR_STATUS_BY_CODE = {s.code: s for s in VENDOR_STATUSES}

FEEDBACK_STATUS_CHOICES = [(s.code, s.label) for s in FEEDBACK_STATUSES]
VENDOR_STATUS_CHOICES = [(s.code, s.label) for s in VENDOR_STATUSES]
