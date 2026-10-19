import pytest

from tracker.statuses import (
    CLOSED,
    FEEDBACK_STATUS_BY_CODE,
    FEEDBACK_STATUS_CHOICES,
    FEEDBACK_STATUSES,
    IN_ANALYSIS,
    NEW,
    RETEST_STAFF,
    RETEST_USER,
    SENT_TO_VENDOR,
    TEST_FAILED,
    TEST_PASSED,
    TO_REPLAY_WITH_USER,
    VENDOR_STATUS_BY_CODE,
    VENDOR_STATUS_CHOICES,
    VENDOR_STATUSES,
    StatusCategory,
)


def test_feedback_display_order_is_the_workflow_order():
    assert [s.code for s in FEEDBACK_STATUSES] == [
        NEW,
        IN_ANALYSIS,
        TO_REPLAY_WITH_USER,
        SENT_TO_VENDOR,
        RETEST_STAFF,
        RETEST_USER,
        TEST_FAILED,
        TEST_PASSED,
        CLOSED,
    ]


def test_feedback_status_codes_are_unique():
    codes = [s.code for s in FEEDBACK_STATUSES]
    assert len(codes) == len(set(codes))


def test_feedback_status_codes_fit_the_future_model_field():
    assert all(len(s.code) <= 30 for s in FEEDBACK_STATUSES)


def test_only_test_passed_and_closed_are_final():
    assert {s.code for s in FEEDBACK_STATUSES if s.is_final} == {TEST_PASSED, CLOSED}


def test_new_is_the_only_todo_status():
    assert [s.code for s in FEEDBACK_STATUSES if s.category is StatusCategory.TODO] == [NEW]


@pytest.mark.parametrize("status", FEEDBACK_STATUSES, ids=lambda s: s.code)
def test_feedback_lookup_by_code(status):
    assert FEEDBACK_STATUS_BY_CODE[status.code] is status


def test_feedback_choices_match_definitions():
    assert [(s.code, s.label) for s in FEEDBACK_STATUSES] == FEEDBACK_STATUS_CHOICES


def test_vendor_statuses():
    assert [s.code for s in VENDOR_STATUSES] == ["in_progress", "to_test", "closed", "blocked"]


@pytest.mark.parametrize("status", VENDOR_STATUSES, ids=lambda s: s.code)
def test_vendor_lookup_by_code(status):
    assert VENDOR_STATUS_BY_CODE[status.code] is status


def test_vendor_choices_match_definitions():
    assert [(s.code, s.label) for s in VENDOR_STATUSES] == VENDOR_STATUS_CHOICES
