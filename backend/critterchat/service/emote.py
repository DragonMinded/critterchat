import io
from PIL import Image
from typing import Dict, cast

from ..config import Config
from ..data import Data, Emote
from .attachment import AttachmentService


class EmoteServiceException(Exception):
    pass


class EmoteService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def get_all_emotes(self) -> Dict[str, Emote]:
        emotes = self.__data.attachment.get_emotes()
        results: Dict[str, Emote] = {}

        for emote in emotes:
            url = self.__attachments.get_attachment_url(emote.attachmentid)
            results[emote.alias] = Emote(url, (cast(int, emote.metadata["width"]), cast(int, emote.metadata["height"])))
        return results

    def validate_emote(self, alias: str) -> bool:
        # First, sanitize the name of the emote.
        alias = alias.lower()
        for c in alias:
            if c not in "abcdefghijklmnopqrstuvwxyz0123456789-_":
                raise EmoteServiceException("Invalid emote name!")

        emote = self.__data.attachment.get_emote(alias)
        if not emote:
            return False

        attachment = self.__attachments.get_attachment_data(emote.attachmentid)
        return attachment is not None

    def add_emote(self, alias: str, data: bytes) -> None:
        # First, sanitize the name of the emote.
        alias = alias.lower()
        for c in alias:
            if c not in "abcdefghijklmnopqrstuvwxyz0123456789-_":
                raise EmoteServiceException("Invalid emote name!")

        # Now, make sure that there's not already one with this name.
        emote = self.__data.attachment.get_emote(alias)
        if emote:
            raise EmoteServiceException("Emote name already in use!")

        try:
            img = Image.open(io.BytesIO(data))
        except Exception:
            raise EmoteServiceException("Unsupported image provided for emote!")

        width, height = img.size
        content_type = img.get_format_mimetype()
        if not content_type:
            raise EmoteServiceException("Unsupported image provided for emote!")
        content_type = content_type.lower()
        if content_type not in AttachmentService.SUPPORTED_IMAGE_TYPES:
            raise EmoteServiceException("Unsupported image provided for emote!")

        # Now, create a new attachment, upload the data to it, and then link the emote.
        attachmentid = self.__data.attachment.insert_attachment(
            self.__config.attachments.system,
            content_type,
            None,
            {
                'width': width,
                'height': height,
            },
        )
        if attachmentid is None:
            raise EmoteServiceException("Could not create new emote!")

        self.__attachments.put_attachment_data(attachmentid, data)

        # Now, link it to the emote.
        self.__data.attachment.add_emote(alias, attachmentid)

    def drop_emote(self, alias: str) -> None:
        # First, sanitize the name of the emote.
        alias = alias.lower()
        for c in alias:
            if c not in "abcdefghijklmnopqrstuvwxyz0123456789-_":
                raise EmoteServiceException("Invalid emote name!")

        # Now, make sure that there's already one with this name.
        emote = self.__data.attachment.get_emote(alias)
        if not emote:
            raise EmoteServiceException("Emote does not exist!")

        # Now, delete the emote link, delete the data from our backend, and delete the attachment.
        self.__data.attachment.remove_emote(emote.alias)
        self.__attachments.delete_attachment_data(emote.attachmentid)
        self.__data.attachment.remove_attachment(emote.attachmentid)
