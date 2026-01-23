import io
import urllib.request
from flask import Blueprint, request
from PIL import Image
from typing import Dict, Optional

from .app import UserException, app, static_location, templates_location, loginrequired, jsonify, g
from ..data import Attachment
from ..service import AttachmentService


upload = Blueprint(
    "upload",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


SUPPORTED_IMAGE_TYPES = {"image/apng", "image/gif", "image/jpeg", "image/png", "image/webp"}


@upload.route("/upload/icon", methods=["POST"])
@loginrequired
@jsonify
def icon_upload() -> Dict[str, object]:
    return _icon_upload("room icon")


@upload.route("/upload/avatar", methods=["POST"])
@loginrequired
@jsonify
def avatar_upload() -> Dict[str, object]:
    return _icon_upload("avatar")


def _icon_upload(uploadtype: str) -> Dict[str, object]:
    attachmentservice = AttachmentService(g.config, g.data)
    body = request.get_data(as_text=True)
    icon: Optional[bytes] = None

    if body and "," in body:
        # Verify that it's a reasonable icon.
        header, b64data = body.split(",", 1)
        if not header.startswith("data:") or not header.endswith("base64"):
            raise UserException(f'Chosen {uploadtype} is not a valid image.')

        actual_length = (len(b64data) / 4) * 3
        if actual_length > g.config.limits.icon_size * 1024:
            raise UserException(f'Chosen {uploadtype} file size is too large. {uploadtype.capitalize()}s cannot be larger than {g.config.limits.icon_size}kb.')

        with urllib.request.urlopen(body) as fp:
            icon = fp.read()

    if not icon:
        raise UserException(f'{uploadtype.capitalize()} data corrupt or not provided in upload.')

    try:
        img = Image.open(io.BytesIO(icon))
    except Exception:
        raise UserException(f"Unsupported image provided for {uploadtype}.")

    width, height = img.size

    if width > AttachmentService.MAX_ICON_WIDTH or height > AttachmentService.MAX_ICON_HEIGHT:
        raise UserException(f"Invalid image size for {uploadtype}. {uploadtype.capitalize()}s must be a maximum of {AttachmentService.MAX_ICON_WIDTH}x{AttachmentService.MAX_ICON_HEIGHT}")
    if width != height:
        raise UserException(f"{uploadtype.capitalize()} image is not square.")

    content_type = img.get_format_mimetype()
    if not content_type:
        raise UserException(f"{uploadtype.capitalize()} image is an unrecognized format.")
    content_type = content_type.lower()
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise UserException(f"{uploadtype.capitalize()} image is an unrecognized format.")

    attachmentid = attachmentservice.create_attachment(content_type, None)
    if attachmentid is None:
        raise Exception(f"Could not insert new {uploadtype}.")
    attachmentservice.put_attachment_data(attachmentid, icon)

    return {'attachmentid': Attachment.from_id(attachmentid)}


app.register_blueprint(upload)
