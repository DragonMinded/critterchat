import tempfile
import urllib.request
from flask import Blueprint, request
from pydub import AudioSegment  # type: ignore
from pydub.exceptions import CouldntDecodeError  # type: ignore
from typing import Dict, List, Optional

from .app import UserException, app, static_location, templates_location, loginrequired, jsonify, g
from ..data import Attachment, UserNotification
from ..service import AttachmentService, AttachmentServiceUnsupportedImageException, AttachmentServiceInvalidSizeException


upload = Blueprint(
    "upload",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


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
    # Ensure that we only allow certain size uploads.
    request.max_content_length = (((g.config.limits.icon_size * 1024) * 4) / 3) + 1024

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
        raise Exception(f'{uploadtype.capitalize()} data corrupt or not provided in upload.')

    try:
        icon, width, height, content_type = attachmentservice.prepare_attachment_image(
            icon,
            AttachmentService.MAX_ICON_WIDTH,
            AttachmentService.MAX_ICON_HEIGHT,
        )
    except AttachmentServiceUnsupportedImageException:
        raise UserException(f"{uploadtype.capitalize()} image is an unrecognized format.")
    except AttachmentServiceInvalidSizeException:
        raise UserException(f"Invalid image size for {uploadtype}. {uploadtype.capitalize()}s must be a maximum of {AttachmentService.MAX_ICON_WIDTH}x{AttachmentService.MAX_ICON_HEIGHT}")

    if width != height:
        raise UserException(f"{uploadtype.capitalize()} image is not square.")

    attachmentid = attachmentservice.create_attachment(content_type, None, {'width': width, 'height': height})
    if attachmentid is None:
        raise Exception(f"Could not insert new {uploadtype}.")
    attachmentservice.put_attachment_data(attachmentid, icon)

    return {'attachmentid': Attachment.from_id(attachmentid)}


@upload.route("/upload/notifications", methods=["POST"])
@loginrequired
@jsonify
def notifications_upload() -> Dict[str, object]:
    # Ensure that we only allow certain size uploads.
    request.max_content_length = ((((g.config.limits.notification_size * 1024) * 4) / 3) + 1024) * len(UserNotification)

    attachmentservice = AttachmentService(g.config, g.data)
    body = request.json or {}

    if not isinstance(body, dict):
        raise Exception("Notification data corrupt or not provided in upload.")

    new_notif_sounds: Dict[str, bytes] = {}
    notif_dict = body.get('notif_sounds', {}) or {}

    # First, load the data and attempt to validate it.
    if isinstance(notif_dict, dict):
        for name, data in notif_dict.items():
            if not isinstance(name, str) or not isinstance(data, str):
                raise Exception("Notification data corrupt or not provided in upload.")
            if "," not in data:
                raise Exception("Notification data corrupt or not provided in upload.")

            # Verify that it's a reasonable sound.
            header, b64data = data.split(",", 1)
            if not header.startswith("data:") or not header.endswith("base64"):
                raise UserException('Chosen notification is not a valid audio file.')

            actual_length = (len(b64data) / 4) * 3
            if actual_length > g.config.limits.notification_size * 1024:
                raise UserException(f'Chosen notification file size is too large. Notifications cannot be larger than {g.config.limits.notification_size}kb.')

            with urllib.request.urlopen(data) as fp:
                notif_data = fp.read()

            new_notif_sounds[name] = notif_data

    # Now, convert to mp3 and attach as attachments.
    response: Dict[str, str] = {}
    for alias, data in new_notif_sounds.items():
        try:
            UserNotification[alias]
        except KeyError:
            raise Exception("Notification key unrecognized, cannot set notification.")

        try:
            with tempfile.NamedTemporaryFile(delete_on_close=False) as fp1:
                fp1.write(data)
                fp1.close()

                segment = AudioSegment.from_file(fp1.name)

                with tempfile.NamedTemporaryFile(delete_on_close=False) as fp2:
                    fp2.close()

                    segment.export(fp2.name, format="mp3")

                    with open(fp2.name, "rb") as bfp:
                        actual_data = bfp.read()

                        attachmentid = attachmentservice.create_attachment("audio/mpeg", None, {})
                        if attachmentid is None:
                            raise Exception("Could not insert new user notification sound!")
                        attachmentservice.put_attachment_data(attachmentid, actual_data)

                        response[alias] = Attachment.from_id(attachmentid)

        except CouldntDecodeError:
            raise UserException("Unsupported audio provided for user notification.")

    # Finally, return all the attachment IDs.
    return {"notif_sounds": response}


@upload.route("/upload/attachments", methods=["POST"])
@loginrequired
@jsonify
def attachments_upload() -> Dict[str, object]:
    # Ensure that we only allow certain size uploads.
    request.max_content_length = ((((g.config.limits.attachment_size * 1024) * 4) / 3) + 2048) * g.config.limits.attachment_max

    attachmentservice = AttachmentService(g.config, g.data)
    body = request.json or {}

    if not isinstance(body, dict):
        raise Exception("Attachment data corrupt or not provided in upload.")

    atchlist = body.get('attachments', [])
    if not isinstance(atchlist, list):
        raise Exception("Attachment data corrupt or not provided in upload.")

    attachmentids: List[str] = []
    for atch in atchlist:
        if not isinstance(atch, dict):
            raise Exception("Attachment data corrupt or not provided in upload.")

        filename = str(atch.get('filename', ''))
        rawdata = str(atch.get('data', ''))
        if not filename or not rawdata or "," not in rawdata:
            raise Exception("Attachment data corrupt or not provided in upload.")

        if "\\" in filename:
            _, filename = filename.rsplit("\\", 1)
        if "/" in filename:
            _, filename = filename.rsplit("/", 1)

        # TODO: At some point we'll support arbitrary attachments, but for now limit
        # to known image types.

        header, b64data = rawdata.split(",", 1)
        if not header.startswith("data:") or not header.endswith("base64"):
            raise UserException(f'Chosen attachment {filename} is not valid!')

        actual_length = (len(b64data) / 4) * 3
        if actual_length > g.config.limits.attachment_size * 1024:
            raise UserException(f'Chosen attachment {filename} file size is too large. Attachments cannot be larger than {g.config.limits.attachment_size}kb.')

        with urllib.request.urlopen(rawdata) as fp:
            attachmentdata = fp.read()

        # Now, verify the image is actually loadable and the right mimetype. Stop
        # people from trying to abuse uploads to store executables or zip files.
        try:
            attachmentdata, width, height, content_type = attachmentservice.prepare_attachment_image(attachmentdata)
        except AttachmentServiceUnsupportedImageException:
            raise UserException(f'Chosen attachment {filename} is not a supported image.')

        # The image is validated at this point, so we can attach it and return the ID.
        attachmentid = attachmentservice.create_attachment(content_type, filename, {'width': width, 'height': height})
        if attachmentid is None:
            raise Exception("Could not insert message attachment!")
        attachmentservice.put_attachment_data(attachmentid, attachmentdata)
        attachmentids.append(Attachment.from_id(attachmentid))

    return {"attachments": attachmentids}


app.register_blueprint(upload)
