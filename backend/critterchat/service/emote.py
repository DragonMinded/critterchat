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
            url = self.__attachments.get_attachment_url("emote", emote.attachment_id)
            results[emote.alias] = url
        return results
