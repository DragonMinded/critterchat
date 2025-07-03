from flask import Blueprint, Response

from .app import cacheable, static_location, templates_location, g
from ..data import Data, Attachment
from ..service import AttachmentService


attachments = Blueprint(
    "attachments",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@attachments.route("/attachments/<attachment>")
@cacheable(86400)
def get_attachment(attachment: str) -> Response:
    if "_" not in attachment:
        return Response("Attachment not found", 404)

    _, aid = attachment.split("_", 1)
    if "." in aid:
        aid, _ = attachment.split(".", 1)

    # Look up and return data for attachment.
    data = Data(g.config)
    attachmentservice = AttachmentService(g.config, data)

    attachmentid = Attachment.to_id(aid)
    if attachmentid is not None:
        response = attachmentservice.get_attachment_data(attachmentid)
        if response:
            mime_type, attachmentbytes = response
            return Response(attachmentbytes, content_type=mime_type)

    return Response("Attachment not found", 404)
