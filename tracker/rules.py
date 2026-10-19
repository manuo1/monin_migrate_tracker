"""State-change rules for feedbacks.

Principle: this module DECIDES and never writes to the database. `services.py` applies the decisions (through the
status change entry point, so history is written) and views may query it. Each rule has an identifier, an explanation
and a function. The statuses themselves (label, color, category) are defined in `statuses.py`.

Design choice: status changes are MANUAL (staff does them while triaging), except what is listed here. Staff follows
the vendor's Jira and judges case by case (one vendor ticket "To test" may cover several feedbacks, some of which are
considered tested without being retested one by one), so retesting is not automated.

ACTIVE RULES
  T1  Transmission to the vendor: when a vendor ticket is added to the links of a feedback that is "new" (created
      from the feedback, associated to an existing ticket, or chosen while triaging), the feedback becomes "sent to
      vendor". Applied by the service that updates vendor links, whatever the entry path. While triaging, if staff
      picks a status other than "new" themselves, the choice is respected (the rule only applies to a feedback still
      "new" once the choice is taken into account).
  T2  Answer to a retest (a right, not an automatic change): a feedback "retest (user)" shows a comment box and two
      buttons on its page. This is the only way a non-staff user changes a status. Available to the feedback's
      author and to staff.
        Test OK -> "test passed", closure reason "fixed" (comment optional).
        Test KO -> "test failed" (comment mandatory: say what is wrong).
      Moving a feedback to "retest (user)" stays manual (triage).

Everything else is free: a manual status change is not validated and nothing else is automatic.
(The "reproduced" flag was removed: a reproduced problem is deduced from a linked vendor ticket; a problem that is not
reproduced is expressed by the status "to replay with user", the closure reason or a comment.)

ARCHIVE: removed rules (kept as a reference for writing use cases)
  R1  Closing: a final status required a reason; closing, reopening or changing the reason required a public comment.
  R2  "Sent to vendor" required a linked vendor ticket.
  R3  Retest answer: author only, when the status was "retest (user)". (taken back and extended to staff in T2)
  R4  Retest answer: OK -> "test passed" (reason "fixed"), KO -> "test failed" (comment mandatory). (taken back in T2)
  R5  Automatic closing of a feedback whose linked vendor tickets were all closed.
  R6  Propagation of a vendor status change: "to test" -> "retest (staff)"; vendor neither to test nor closed -> back to
      "sent to vendor"; vendor closed -> R5. (Tried then dropped: staff decides by hand.)
  R7  Manual status change reserved to staff (still enforced by the views: triage block).
"""

from enum import StrEnum
from typing import Protocol

from .choices import ClosureReason
from .statuses import NEW, RETEST_USER, SENT_TO_VENDOR, TEST_FAILED, TEST_PASSED


class _Feedback(Protocol):
    status: str
    author_id: int | None


class _User(Protocol):
    id: int | None
    is_staff: bool


class RetestAnswer(StrEnum):
    OK = "ok"
    KO = "ko"


# T1: feedback statuses from which adding a vendor ticket triggers the transmission.
TRANSMISSIBLE_STATUSES = {NEW}

# T2: retest answer -> (feedback status, closure reason).
RETEST_OUTCOMES = {
    RetestAnswer.OK: (TEST_PASSED, ClosureReason.FIXED),
    RetestAnswer.KO: (TEST_FAILED, ""),
}


def status_after_vendor_link(feedback: _Feedback) -> str | None:
    """T1. Status the feedback must take after a vendor ticket is added, or None if unchanged."""
    if feedback.status in TRANSMISSIBLE_STATUSES:
        return SENT_TO_VENDOR
    return None


def retest_is_open(feedback: _Feedback, user: _User) -> bool:
    """T2. True if `user` can answer the retest: status "retest (user)", and user is the author or staff."""
    if feedback.status != RETEST_USER:
        return False
    if user.is_staff:
        return True
    return user.id is not None and feedback.author_id == user.id


def retest_outcome(answer: str) -> tuple[str, str]:
    """T2. (status, closure reason) for the answer "ok" or "ko"; ValueError if the answer is unknown."""
    try:
        parsed = RetestAnswer(answer)
    except ValueError:
        raise ValueError(f"Unknown retest answer: {answer!r}") from None
    return RETEST_OUTCOMES[parsed]


def comment_required(answer: str) -> bool:
    """T2. A failed test must be explained."""
    return answer == RetestAnswer.KO
