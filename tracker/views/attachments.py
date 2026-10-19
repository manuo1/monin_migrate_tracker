import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from ..models import Attachment

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
