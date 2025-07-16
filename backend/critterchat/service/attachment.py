import mimetypes
import os
from typing import Optional, Tuple
from typing_extensions import Final

from ..config import Config
from ..data import Data, Attachment, Action, User, Occupant, Room, AttachmentID, DefaultAvatarID, DefaultRoomID
from ..http.static import default_avatar, default_room


# Guess we need to init this. Feel like I'm doing embedded again.
mimetypes.init()


class AttachmentServiceException(Exception):
    pass


class AttachmentService:
    MAX_ICON_WIDTH: Final[int] = 256
    MAX_ICON_HEIGHT: Final[int] = 256

    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data

    def get_content_type(self, filename: str) -> str:
        try:
            return mimetypes.types_map[os.path.splitext(filename)[1]]
        except Exception:
            return "application/octet-stream"

    def create_attachment(self, content_type: str) -> Optional[AttachmentID]:
        return self.__data.attachment.insert_attachment(self.__config.attachments.system, content_type)

    def destroy_attachment(self, attachmentid: AttachmentID) -> None:
        self.delete_attachment_data(attachmentid)
        self.__data.attachment.remove_attachment(attachmentid)

    def get_attachment_data(self, attachmentid: AttachmentID) -> Optional[Tuple[str, bytes]]:
        # Check for default avatar.
        if attachmentid == DefaultAvatarID:
            with open(default_avatar, "rb") as bfp:
                data = bfp.read()
                enc = self.get_content_type(default_avatar)
                return enc, data
        if attachmentid == DefaultRoomID:
            with open(default_room, "rb") as bfp:
                data = bfp.read()
                enc = self.get_content_type(default_room)
                return enc, data

        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            return None

        if attachment.system == "local":
            # Local storage, look up the storage directory and return that data.
            directory = self.__config.attachments.directory
            if not directory:
                raise AttachmentServiceException("Cannot find directory for local attachment storage!")

            path = os.path.join(directory, str(attachmentid))
            try:
                with open(path, "rb") as bfp:
                    data = bfp.read()
                    return attachment.content_type, data
            except FileNotFoundError:
                return None
        else:
            # Unknown backend, throw.
            raise AttachmentServiceException("Unrecognized backend system!")

    def put_attachment_data(self, attachmentid: AttachmentID, data: bytes) -> None:
        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            return

        if attachment.system == "local":
            # Local storage, look up the storage directory and write the data.
            directory = self.__config.attachments.directory
            if not directory:
                raise AttachmentServiceException("Cannot find directory for local attachment storage!")

            path = os.path.join(directory, str(attachmentid))
            with open(path, "wb") as bfp:
                bfp.write(data)
        else:
            # Unknown backend, throw.
            raise AttachmentServiceException("Unrecognized backend system!")

    def delete_attachment_data(self, attachmentid: AttachmentID) -> None:
        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            return

        if attachment.system == "local":
            # Local storage, look up the storage directory and write the data.
            directory = self.__config.attachments.directory
            if not directory:
                raise AttachmentServiceException("Cannot find directory for local attachment storage!")

            path = os.path.join(directory, str(attachmentid))
            os.remove(path)
        else:
            # Unknown backend, throw.
            raise AttachmentServiceException("Unrecognized backend system!")

    def resolve_user_icon(self, user: User) -> User:
        if user.iconid is None:
            user.icon = self.get_attachment_url(DefaultAvatarID)
        else:
            user.icon = self.get_attachment_url(user.iconid)
        return user

    def resolve_occupant_icon(self, occupant: Occupant) -> Occupant:
        if occupant.iconid is None:
            occupant.icon = self.get_attachment_url(DefaultAvatarID)
        else:
            occupant.icon = self.get_attachment_url(occupant.iconid)
        return occupant

    def resolve_action_icon(self, action: Action) -> Action:
        self.resolve_occupant_icon(action.occupant)
        return action

    def resolve_chat_icon(self, room: Room) -> Room:
        if room.iconid is None:
            room.icon = self.get_attachment_url(DefaultAvatarID)
        else:
            room.icon = self.get_attachment_url(room.iconid)
        return room

    def resolve_room_icon(self, room: Room) -> Room:
        if room.iconid is None:
            room.icon = self.get_attachment_url(DefaultRoomID)
        else:
            room.icon = self.get_attachment_url(room.iconid)
        return room

    def get_attachment_url(self, attachmentid: AttachmentID) -> str:
        prefix = self.__config.attachments.prefix
        if prefix[-1] == "/":
            prefix = prefix[:-1]
        return f"{prefix}/{Attachment.from_id(attachmentid)}"
