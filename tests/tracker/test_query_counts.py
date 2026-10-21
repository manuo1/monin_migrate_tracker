"""N+1 audit: the number of SQL queries of each page must not grow with the amount of data displayed."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory

pytestmark = pytest.mark.django_db


def count_queries(client, url):
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    assert response.status_code == 200
    return len(context)


def assert_constant_queries(client, url, grow):
    """Query count measured with a little data, then again after `grow()` added a lot more: it must not change."""
    client.get(url)  # warm-up (caches, session)
    before = count_queries(client, url)
    grow()
    after = count_queries(client, url)
    assert after == before, f"{url}: {before} queries before, {after} after adding data (N+1)"


@pytest.fixture
def staff(client):
    account = StaffFactory()
    client.force_login(account)
    return account


def add_linked_feedbacks(count, ticket=None):
    """`count` feedbacks (each with its own author), each linked to `ticket` (if any) and to one other ticket."""
    for _ in range(count):
        feedback = FeedbackFactory(author=UserFactory())
        feedback.vendor_tickets.add(VendorTicketFactory())
        if ticket:
            feedback.vendor_tickets.add(ticket)


def test_feedback_list(client, staff):
    add_linked_feedbacks(2)
    assert_constant_queries(client, reverse("feedback_list"), lambda: add_linked_feedbacks(10))


def test_feedback_list_for_a_regular_user(client):
    user = UserFactory()
    client.force_login(user)

    def grow():
        for _ in range(10):
            FeedbackFactory(author=user).vendor_tickets.add(VendorTicketFactory())

    FeedbackFactory(author=user).vendor_tickets.add(VendorTicketFactory())
    assert_constant_queries(client, reverse("feedback_list"), grow)


def test_vendor_ticket_list(client, staff):
    ticket = VendorTicketFactory()
    add_linked_feedbacks(2, ticket)
    assert_constant_queries(
        client, reverse("vendor_ticket_list"), lambda: add_linked_feedbacks(10, VendorTicketFactory())
    )


def test_vendor_ticket_detail(client, staff):
    ticket = VendorTicketFactory()
    add_linked_feedbacks(2, ticket)

    def grow():
        add_linked_feedbacks(10, ticket)
        for _ in range(10):
            ticket.events.create(author=UserFactory(), text="Un événement")

    assert_constant_queries(client, reverse("vendor_ticket_detail", args=[ticket.pk]), grow)


def test_vendor_ticket_associate(client, staff):
    feedback = FeedbackFactory()
    add_linked_feedbacks(2, VendorTicketFactory())

    def grow():
        add_linked_feedbacks(10, VendorTicketFactory())

    assert_constant_queries(client, reverse("vendor_ticket_associate", args=[feedback.pk]), grow)


def test_feedback_detail(client, staff):
    feedback = FeedbackFactory()

    def grow():
        for _ in range(10):
            author = UserFactory()
            feedback.comments.create(author=author, text="Un commentaire")
            feedback.events.create(author=author, text="Un événement")
            feedback.status_history.create(author=author, status="in_analysis")
            feedback.attachments.create(file="feedbacks/2026/01/capture.png")
            feedback.vendor_tickets.add(VendorTicketFactory())

    feedback.status_history.create(author=staff, status="new")
    assert_constant_queries(client, reverse("feedback_detail", args=[feedback.pk]), grow)
