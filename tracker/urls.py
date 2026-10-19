from django.urls import path

from .views import attachments, feedbacks

urlpatterns = [
    path("", feedbacks.feedback_list, name="feedback_list"),
    path("feedbacks/<int:pk>/", feedbacks.feedback_detail, name="feedback_detail"),
    path("feedbacks/<int:pk>/comment/", feedbacks.add_comment, name="add_comment"),
    path("feedbacks/<int:pk>/retest/", feedbacks.retest, name="retest"),
    path("attachments/<int:pk>/", attachments.attachment_file, name="attachment_file"),
]
