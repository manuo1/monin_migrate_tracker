import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .. import services
from ..models import Attachment, Feedback
from .common import can_add_attachments, staff_required

# Types the browser may display inline. Everything else (HTML, SVG, scripts...) is forced to download, because an
# uploaded file opened inline from our own origin could run scripts in a logged-in session.
INLINE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "application/pdf",
}


@login_required
def attachment_file(request, pk):
    """Serve an attachment to any logged-in user (never as a public media URL)."""
    attachment = get_object_or_404(Attachment, pk=pk)
    content_type = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
    try:
        stream = attachment.file.open("rb")
    except FileNotFoundError:
        raise Http404("Fichier introuvable.") from None
    return FileResponse(
        stream,
        content_type=content_type,
        as_attachment=content_type not in INLINE_CONTENT_TYPES,
        filename=attachment.name,
    )


@login_required
@require_POST
def add_attachments(request, pk):
    """The author or staff adds files to a feedback (403 otherwise)."""
    feedback = get_object_or_404(Feedback, pk=pk)
    if not can_add_attachments(request.user, feedback):
        raise PermissionDenied
    files = request.FILES.getlist("files")
    if files:
        services.add_attachments(feedback, files, request.user)
        messages.success(request, f"{len(files)} pièce(s) jointe(s) ajoutée(s).")
    else:
        messages.error(request, "Aucun fichier sélectionné.")
    return redirect("feedback_detail", pk=pk)


@staff_required
@require_POST
def remove_attachment(request, pk, attachment_id):
    """Staff detaches a file from a feedback; the file itself stays on disk."""
    feedback = get_object_or_404(Feedback, pk=pk)
    attachment = get_object_or_404(feedback.attachments, pk=attachment_id)
    services.remove_attachment(feedback, attachment, request.user)
    messages.success(request, "Pièce jointe supprimée.")
    return redirect("feedback_detail", pk=pk)
