from types import SimpleNamespace

import pytest

from tracker import rules
from tracker.choices import ClosureReason
from tracker.statuses import (
    FEEDBACK_STATUSES,
    NEW,
    RETEST_USER,
    SENT_TO_VENDOR,
    TEST_FAILED,
    TEST_PASSED,
)

ALL_CODES = [s.code for s in FEEDBACK_STATUSES]


def make_feedback(status=NEW, author_id=1):
    return SimpleNamespace(status=status, author_id=author_id)


def make_user(user_id=1, is_staff=False):
    return SimpleNamespace(id=user_id, is_staff=is_staff)


# --- T1: transmission to the vendor ---


@pytest.mark.parametrize("status", ALL_CODES)
def test_t1_only_a_new_feedback_becomes_sent_to_vendor(status):
    expected = SENT_TO_VENDOR if status == NEW else None
    assert rules.status_after_vendor_link(make_feedback(status=status)) == expected


# --- T2: answer to a retest request ---


def test_t2_author_can_answer_when_retest_is_requested_from_the_user():
    assert rules.retest_is_open(make_feedback(RETEST_USER, author_id=7), make_user(7)) is True


def test_t2_staff_can_answer_even_when_not_the_author():
    assert rules.retest_is_open(make_feedback(RETEST_USER, author_id=7), make_user(99, is_staff=True)) is True


def test_t2_another_user_cannot_answer():
    assert rules.retest_is_open(make_feedback(RETEST_USER, author_id=7), make_user(8)) is False


@pytest.mark.parametrize("status", [c for c in ALL_CODES if c != RETEST_USER])
def test_t2_nobody_can_answer_in_any_other_status(status):
    feedback = make_feedback(status, author_id=7)
    assert rules.retest_is_open(feedback, make_user(7)) is False
    assert rules.retest_is_open(feedback, make_user(99, is_staff=True)) is False


def test_t2_anonymous_user_cannot_answer_even_if_ids_are_both_missing():
    assert rules.retest_is_open(make_feedback(RETEST_USER, author_id=None), make_user(None)) is False


def test_t2_ok_answer_passes_the_test_and_closes_as_fixed():
    assert rules.retest_outcome("ok") == (TEST_PASSED, ClosureReason.FIXED)


def test_t2_ko_answer_fails_the_test_without_closure_reason():
    assert rules.retest_outcome("ko") == (TEST_FAILED, "")


@pytest.mark.parametrize("answer", ["", "maybe", "OK", None])
def test_t2_unknown_answer_is_rejected(answer):
    with pytest.raises(ValueError, match="Unknown retest answer"):
        rules.retest_outcome(answer)


def test_t2_a_comment_is_required_only_for_a_ko():
    assert rules.comment_required("ko") is True
    assert rules.comment_required("ok") is False
