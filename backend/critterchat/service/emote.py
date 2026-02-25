from typing import cast

from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict
from ..config import Config
from ..data import Data, Emote, MetadataType
from .attachment import AttachmentService, AttachmentServiceUnsupportedImageException, AttachmentServiceException


class EmoteServiceException(Exception):
    pass


_valid_emojis: set[str] | None = None


class EmoteService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def get_all_emojis(self) -> set[str]:
        # Returns all valid emojis we know about, given our categories. Not used for much, but
        # used when validating reactions for example.
        global _valid_emojis
        if _valid_emojis:
            return _valid_emojis

        emojis = {
            **get_emoji_unicode_dict('en'),
            **get_aliases_unicode_dict(),
        }

        def strip_colons(string: str) -> str:
            if string and string[0] == ":" and string[-1] == ":":
                return string[1:-1]
            return string

        _valid_emojis = set(strip_colons(s) for s in emojis.keys())
        return _valid_emojis

    def get_all_emotes(self) -> dict[str, Emote]:
        emotes = self.__data.attachment.get_emotes()
        results: dict[str, Emote] = {}

        for emote in emotes:
            url = self.__attachments.get_attachment_url(emote.attachmentid)
            results[emote.alias] = Emote(
                url,
                (cast(int, emote.metadata[MetadataType.WIDTH]), cast(int, emote.metadata[MetadataType.HEIGHT])),
            )
        return results

    def validate_emote(self, alias: str, check_data: bool = False) -> bool:
        # First, sanitize the name of the emote.
        alias = alias.lower()
        for c in alias:
            if c not in "abcdefghijklmnopqrstuvwxyz0123456789-_":
                raise EmoteServiceException("Invalid emote name!")

        emote = self.__data.attachment.get_emote(alias)
        if not emote:
            return False

        if not check_data:
            return True

        # This can be expensive depending on the backend, so only do it when necessary.
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
            data, width, height, content_type = self.__attachments.prepare_attachment_image(data)
        except AttachmentServiceUnsupportedImageException:
            raise EmoteServiceException("Unsupported image provided for emote!")
        except AttachmentServiceException as e:
            raise EmoteServiceException(str(e))

        # Now, create a new attachment, upload the data to it, and then link the emote.
        attachmentid = self.__data.attachment.insert_attachment(
            self.__config.attachments.system,
            content_type,
            None,
            {
                MetadataType.WIDTH: width,
                MetadataType.HEIGHT: height,
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
