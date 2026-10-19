"""Feedback timeline: comments, status changes and other events in one thread, newest first."""

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth.models import AbstractBaseUser

from .statuses import FEEDBACK_STATUS_BY_CODE


@dataclass(frozen=True)
class TimelineItem:
    date: datetime
    author: AbstractBaseUser
    is_comment: bool
    text: str


def build_timeline(feedback):
    items = [TimelineItem(c.created_at, c.author, True, c.text) for c in feedback.comments.select_related("author")]
    for index, change in enumerate(feedback.status_history.select_related("author")):
        label = FEEDBACK_STATUS_BY_CODE[change.status].label
        text = f"Ticket créé (statut : {label})" if index == 0 else f"Statut → {label}"
        items.append(TimelineItem(change.date, change.author, False, text))
    items.extend(TimelineItem(e.date, e.author, False, e.text) for e in feedback.events.select_related("author"))
    items.sort(key=lambda item: item.date, reverse=True)
    return items
