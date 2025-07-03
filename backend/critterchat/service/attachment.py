import os
from typing import Optional, Tuple

from ..config import Config
from ..data import Data, Attachment, Action, User, Occupant, Room, AttachmentID, DefaultAvatarID, DefaultRoomID
from ..http.static import default_avatar, default_room


class AttachmentServiceException(Exception):
    pass


class AttachmentService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data

    def get_attachment_data(self, attachmentid: AttachmentID) -> Optional[Tuple[str, bytes]]:
        # Check for default avatar.
        if attachmentid == DefaultAvatarID:
            with open(default_avatar, "rb") as bfp:
                data = bfp.read()
                return "image/png", data
        if attachmentid == DefaultRoomID:
            with open(default_room, "rb") as bfp:
                data = bfp.read()
                return "image/png", data

        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            return None

        system, content_type = attachment
        if system == "local":
            # Local storage, look up the storage directory and return that data.
            directory = self.__config.attachments.directory
            if not directory:
                raise AttachmentServiceException("Cannot find directory for local attachment storage!")

            path = os.path.join(directory, str(attachmentid))
            try:
                with open(path, "rb") as bfp:
                    data = bfp.read()
                    return content_type, data
            except FileNotFoundError:
                return None
        else:
            # Unknown backend, throw.
            raise AttachmentServiceException("Unrecognized backend system!")

    def resolve_user_icon(self, user: User) -> User:
        if user.iconid is None:
            user.icon = self.get_attachment_url("avi", DefaultAvatarID)
        else:
            user.icon = self.get_attachment_url("avi", user.iconid)
        return user

    def resolve_occupant_icon(self, occupant: Occupant) -> Occupant:
        if occupant.iconid is None:
            occupant.icon = self.get_attachment_url("avi", DefaultAvatarID)
        else:
            occupant.icon = self.get_attachment_url("avi", occupant.iconid)
        return occupant

    def resolve_action_icon(self, action: Action) -> Action:
        self.resolve_occupant_icon(action.occupant)
        return action

    def resolve_chat_icon(self, room: Room) -> Room:
        if room.iconid is None:
            room.icon = self.get_attachment_url("room", DefaultAvatarID)
        else:
            room.icon = self.get_attachment_url("room", room.iconid)
        return room

    def resolve_room_icon(self, room: Room) -> Room:
        if room.iconid is None:
            room.icon = self.get_attachment_url("room", DefaultRoomID)
        else:
            room.icon = self.get_attachment_url("room", room.iconid)
        return room

    def get_attachment_url(self, purpose: str, attachmentid: AttachmentID) -> str:
        prefix = self.__config.attachments.prefix
        if prefix[-1] == "/":
            prefix = prefix[:-1]
        return f"{prefix}/{purpose}_{Attachment.from_id(attachmentid)}"
