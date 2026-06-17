import os
from flask import Blueprint, Response

from .app import cacheable, static_location, templates_location, g
from ..data import Data
from ..service import AttachmentService


attachments = Blueprint(
    "attachments",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


BLACKLISTED_TEXT_EXTENSIONS = {
    ".php", ".phtml", ".php3", ".php4", ".php5", ".pl", ".py", ".jsp", ".asp", ".html", ".htm", ".shtml", ".sh", ".cgi",
}


@attachments.route("/attachments/<attachment>")
@cacheable(86400)
def get_attachment(attachment: str) -> Response:
    # Look up and return data for attachment. Manually instantiate data here because
    # we intentionally skipped that for static endpoints in app.py.
    with Data.spawn(g.config) as data:
        attachmentservice = AttachmentService(g.config, data)

        # This is a debug endpoint only, not meant for production use. So, it's fine
        # to pull a little shenanigans here.
        attachmentid = attachmentservice.id_from_path(attachment)
        if attachmentid is not None:
            response = attachmentservice.get_attachment_data(attachmentid)
            if response:
                mime_type, attachmentbytes = response

                # For text attachments, we might need to fix up the mime type here.
                _, ext = os.path.splitext(attachment)
                if ext.lower() in BLACKLISTED_TEXT_EXTENSIONS:
                    mime_type = "text/plain"

                return Response(attachmentbytes, content_type=mime_type)

    return Response("Attachment not found", 404)
