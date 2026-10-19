"""Status definitions for feedbacks and vendor tickets.

Statuses live in code, not in database tables. They feed the `choices` of the model fields.
Adding, renaming or removing a status changes those `choices`: run `makemigrations` (no schema change).
If the code of an existing status changes, a data migration is also needed; a new color or label needs none.

This module only holds definitions. State-change rules live in `rules.py`.
"""

from dataclasses import dataclass
from enum import StrEnum


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
    FeedbackStatus(NEW, "Nouveau", "secondary", StatusCategory.TODO),
    FeedbackStatus(IN_ANALYSIS, "En analyse", "primary", StatusCategory.IN_PROGRESS),
    FeedbackStatus(TO_REPLAY_WITH_USER, "À rejouer avec l'utilisateur", "warning", StatusCategory.IN_PROGRESS),
    FeedbackStatus(SENT_TO_VENDOR, "Transmis Aptean", "info", StatusCategory.IN_PROGRESS),
    FeedbackStatus(RETEST_STAFF, "À retester (staff)", "warning", StatusCategory.IN_PROGRESS),
    FeedbackStatus(RETEST_USER, "À retester (utilisateur)", "primary", StatusCategory.IN_PROGRESS),
    FeedbackStatus(TEST_FAILED, "Test KO", "danger", StatusCategory.IN_PROGRESS),
    FeedbackStatus(TEST_PASSED, "Test OK", "success", StatusCategory.DONE),
    FeedbackStatus(CLOSED, "Clos", "success", StatusCategory.DONE),
]

# Vendor ticket status codes (the status is optional on a vendor ticket: empty string when unknown).
VENDOR_IN_PROGRESS = "in_progress"
VENDOR_TO_TEST = "to_test"
VENDOR_CLOSED = "closed"
VENDOR_BLOCKED = "blocked"

VENDOR_STATUSES = [
    VendorStatus(VENDOR_IN_PROGRESS, "En cours", "primary"),
    VendorStatus(VENDOR_TO_TEST, "À tester", "warning"),
    VendorStatus(VENDOR_CLOSED, "Clos", "success"),
    VendorStatus(VENDOR_BLOCKED, "Bloqué", "danger"),
]

FEEDBACK_STATUS_BY_CODE = {s.code: s for s in FEEDBACK_STATUSES}
VENDOR_STATUS_BY_CODE = {s.code: s for s in VENDOR_STATUSES}

FEEDBACK_STATUS_CHOICES = [(s.code, s.label) for s in FEEDBACK_STATUSES]
VENDOR_STATUS_CHOICES = [(s.code, s.label) for s in VENDOR_STATUSES]
