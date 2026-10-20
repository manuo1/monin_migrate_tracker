from django.urls import path

from .views import attachments, feedbacks, vendor_tickets

urlpatterns = [
    path("", feedbacks.feedback_list, name="feedback_list"),
    path("feedbacks/new/", feedbacks.feedback_create, name="feedback_create"),
    path("feedbacks/<int:pk>/", feedbacks.feedback_detail, name="feedback_detail"),
    path("feedbacks/<int:pk>/edit/", feedbacks.feedback_edit, name="feedback_edit"),
    path("feedbacks/<int:pk>/triage/", feedbacks.feedback_triage, name="feedback_triage"),
    path("feedbacks/<int:pk>/comment/", feedbacks.add_comment, name="add_comment"),
    path("feedbacks/<int:pk>/retest/", feedbacks.retest, name="retest"),
    path("vendor-tickets/", vendor_tickets.vendor_ticket_list, name="vendor_ticket_list"),
    path("vendor-tickets/<int:pk>/", vendor_tickets.vendor_ticket_detail, name="vendor_ticket_detail"),
    path("attachments/<int:pk>/", attachments.attachment_file, name="attachment_file"),
    path("feedbacks/<int:pk>/attachments/", attachments.add_attachments, name="add_attachments"),
    path(
        "feedbacks/<int:pk>/attachments/<int:attachment_id>/remove/",
        attachments.remove_attachment,
        name="remove_attachment",
    ),
]
