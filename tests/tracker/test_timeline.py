import datetime

import pytest

from tests.tracker.factories import FeedbackFactory, UserFactory
from tracker import history
from tracker.models import Comment, FeedbackEvent, StatusChange
from tracker.statuses import IN_ANALYSIS, NEW
from tracker.timeline import build_timeline

pytestmark = pytest.mark.django_db


def at(day):
    return datetime.datetime(2026, 10, day, 12, 0, tzinfo=datetime.UTC)


def test_timeline_of_an_empty_feedback_is_empty():
    assert build_timeline(FeedbackFactory()) == []


def test_timeline_merges_comments_statuses_and_events_newest_first():
    author = UserFactory()
    feedback = FeedbackFactory(author=author)
    history.record_status(feedback, author)  # creation
    feedback.status = IN_ANALYSIS
    history.record_status(feedback, author)
    comment = Comment.objects.create(feedback=feedback, author=author, text="A comment")
    event = FeedbackEvent.objects.create(feedback=feedback, author=author, text="An event")
    first, second = StatusChange.objects.order_by("pk")
    StatusChange.objects.filter(pk=first.pk).update(date=at(1))
    StatusChange.objects.filter(pk=second.pk).update(date=at(3))
    Comment.objects.filter(pk=comment.pk).update(created_at=at(2))
    FeedbackEvent.objects.filter(pk=event.pk).update(date=at(4))

    timeline = build_timeline(feedback)

    assert [(item.text, item.is_comment) for item in timeline] == [
        ("An event", False),
        ("Statut → En analyse", False),
        ("A comment", True),
        ("Ticket créé (statut : Nouveau)", False),
    ]


def test_first_status_row_is_described_as_the_creation():
    author = UserFactory()
    feedback = FeedbackFactory(author=author, status=NEW)
    history.record_status(feedback, author)
    assert [item.text for item in build_timeline(feedback)] == ["Ticket créé (statut : Nouveau)"]
