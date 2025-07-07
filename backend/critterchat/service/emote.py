from typing import Dict

from ..config import Config
from ..data import Data
from .attachment import AttachmentService


class EmoteServiceException(Exception):
    pass


class EmoteService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def get_all_emotes(self) -> Dict[str, str]:
        emotes = self.__data.attachment.get_emotes()
        results: Dict[str, str] = {}

        for emote in emotes:
            url = self.__attachments.get_attachment_url(emote.attachmentid)
            results[emote.alias] = url
        return results

    def add_emote(self, alias: str, content_type: str, data: bytes) -> None:
        # First, sanitize the name of the emote.
        alias = alias.lower()
        for c in alias:
            if c not in "abcdefghijklmnopqrstuvwxyz0123456789-_":
                raise EmoteServiceException("Invalid emote name!")

        # Now, make sure that there's not already one with this name.
        emote = self.__data.attachment.get_emote(alias)
        if emote:
            raise EmoteServiceException("Emote name already in use!")

        # Now, create a new attachment, upload the data to it, and then link the emote.
        attachmentid = self.__data.attachment.insert_attachment(self.__config.attachments.system, content_type)
        if attachmentid is None:
            raise EmoteServiceException("Could not creat new emote!")

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
