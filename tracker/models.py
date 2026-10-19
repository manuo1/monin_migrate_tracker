from django.conf import settings
from django.db import models
from django.utils import timezone

from .choices import ClosureReason, FeedbackType
from .statuses import (
    FEEDBACK_STATUS_BY_CODE,
    FEEDBACK_STATUS_CHOICES,
    NEW,
    VENDOR_STATUS_BY_CODE,
    VENDOR_STATUS_CHOICES,
)


class VendorTicket(models.Model):
    """A ticket of the vendor's Jira (displayed as "Aptean" in the interface)."""

    # Empty until the ticket exists in Jira (NULL, so that several tickets without reference can coexist).
    ref = models.CharField(max_length=50, unique=True, null=True, blank=True)  # noqa: DJ001
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    page = models.CharField(max_length=200, blank=True)
    tab = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=VENDOR_STATUS_CHOICES, blank=True, default="")
    url = models.URLField(blank=True)
    created_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["ref"]

    def __str__(self):
        tab = f" > {self.tab}" if self.tab else ""
        return f"{self.label} · {self.page}{tab}"

    @property
    def label(self):
        """Jira reference, or a placeholder while it is not entered yet."""
        return self.ref or f"Sans réf. (#{self.pk})"

    @property
    def link(self):
        """Stored Jira link, or one built from the reference for tickets created without a link."""
        if self.url:
            return self.url
        return settings.JIRA_BASE_URL + self.ref if self.ref else ""

    @property
    def status_info(self):
        """Vendor status definition (label, color) or None when not set."""
        return VENDOR_STATUS_BY_CODE.get(self.status)


class VendorTicketEvent(models.Model):
    """History of a vendor ticket: field changes, links with feedbacks."""

    ticket = models.ForeignKey(VendorTicket, related_name="events", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date = models.DateTimeField(default=timezone.now)
    text = models.TextField()

    class Meta:
        ordering = ["date", "pk"]

    def __str__(self):
        return f"{self.ticket.label} · {self.text[:50]}"


class Feedback(models.Model):
    """A report made by a tester about a page/tab of the migrated application."""

    type = models.CharField(max_length=20, choices=FeedbackType.choices)
    status = models.CharField(max_length=30, choices=FEEDBACK_STATUS_CHOICES, default=NEW)
    closure_reason = models.CharField(max_length=20, choices=ClosureReason.choices, blank=True)

    page = models.CharField(max_length=200)
    tab = models.CharField(max_length=200, blank=True)
    article_id = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="feedbacks", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    vendor_tickets = models.ManyToManyField(VendorTicket, blank=True, related_name="feedbacks")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        description = self.description[:50].replace("\n", " ")
        article = f" · {self.article_id}" if self.article_id else ""
        tab = f" > {self.tab}" if self.tab else ""
        return f"#{self.pk} · {self.page}{tab}{article} · {description}"

    @property
    def status_info(self):
        """Feedback status definition (label, color, category...)."""
        return FEEDBACK_STATUS_BY_CODE[self.status]


class Attachment(models.Model):
    feedback = models.ForeignKey(Feedback, related_name="attachments", on_delete=models.CASCADE)
    file = models.FileField(upload_to="feedbacks/%Y/%m/")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.file.name.rsplit("/", 1)[-1]

    @property
    def kind(self):
        extension = self.name.rsplit(".", 1)[-1].lower() if "." in self.name else ""
        if extension in {"png", "jpg", "jpeg", "gif", "webp", "bmp"}:
            return "image"
        if extension in {"mp4", "webm", "mov"}:
            return "video"
        if extension == "pdf":
            return "pdf"
        return "other"


class Comment(models.Model):
    feedback = models.ForeignKey(Feedback, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"#{self.feedback_id} · {self.text[:50]}"


class FeedbackEvent(models.Model):
    """Trace of changes other than comments and statuses (links, vendor tickets, attachments, closure reason...)."""

    feedback = models.ForeignKey(Feedback, related_name="events", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date = models.DateTimeField(default=timezone.now)
    text = models.TextField()

    class Meta:
        ordering = ["date", "pk"]

    def __str__(self):
        return f"#{self.feedback_id} · {self.text[:50]}"


class StatusChange(models.Model):
    """Status history of a feedback. The first row is its creation."""

    feedback = models.ForeignKey(Feedback, related_name="status_history", on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=FEEDBACK_STATUS_CHOICES)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "pk"]

    def __str__(self):
        return f"#{self.feedback_id} · {self.status}"
