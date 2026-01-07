import hashlib
import json
import mimetypes
import os
from typing import Dict, Final, Optional, Tuple

from ..config import Config
from ..data import (
    Data,
    Attachment,
    Action,
    ActionType,
    User,
    Occupant,
    Room,
    AttachmentID,
    DefaultAvatarID,
    DefaultRoomID,
    FaviconID,
)
from ..http.static import default_avatar, default_room, default_icon


# Guess we need to init this. Feel like I'm doing embedded again.
mimetypes.init()


class AttachmentServiceException(Exception):
    pass


_hash_to_id_lut: Dict[str, AttachmentID] = {}


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

    def _get_hashed_attachment_name(self, aid: AttachmentID) -> str:
        if aid in {DefaultAvatarID, DefaultRoomID, FaviconID}:
            return Attachment.from_id(aid)

        hashkey = self.__config.attachments.attachment_key
        inval = f"{hashkey}-{Attachment.from_id(aid)}"
        return hashlib.shake_256(inval.encode('utf-8')).hexdigest(20)

    def _get_local_attachment_path(self, aid: AttachmentID) -> str:
        directory = self.__config.attachments.directory
        if not directory:
            raise AttachmentServiceException("Cannot find directory for local attachment storage!")

        return os.path.join(directory, self._get_hashed_attachment_name(aid))

    def create_default_attachments(self) -> None:
        for aid, default in [
            (DefaultAvatarID, default_avatar),
            (DefaultRoomID, default_room),
            (FaviconID, default_icon),
        ]:
            if self.__config.attachments.system == "local":
                # Local storage, copy the system default into the attachment directory if needed.
                path = self._get_local_attachment_path(aid)
                if not os.path.isfile(path):
                    with open(default, "rb") as bfp1:
                        data = bfp1.read()
                    with open(path, "wb") as bfp2:
                        bfp2.write(data)
            else:
                # Unknown backend, throw.
                raise AttachmentServiceException("Unrecognized backend system!")

    def migrate_legacy_attachments(self) -> None:
        if self.__config.attachments.system == "local":
            def _get_legacy_local_attachment_path(aid: AttachmentID) -> str:
                directory = self.__config.attachments.directory
                if not directory:
                    raise AttachmentServiceException("Cannot find directory for local attachment storage!")

                return os.path.join(directory, Attachment.from_id(aid))

            # First, we need to attempt to migrate from pre-hashed to hashed.
            attachments = self.__data.attachment.get_attachments()
            for attachment in attachments:
                # Local storage, copy the system default into the attachment directory if needed.
                oldpath = _get_legacy_local_attachment_path(attachment.id)
                path = self._get_local_attachment_path(attachment.id)
                if (not os.path.isfile(path)) and os.path.isfile(oldpath):
                    with open(oldpath, "rb") as bfp1:
                        data = bfp1.read()
                    with open(path, "wb") as bfp2:
                        bfp2.write(data)
                    os.remove(oldpath)

        else:
            # Unknown backend, throw since we have no known migrations.
            raise AttachmentServiceException("Unrecognized backend system!")

    def id_from_path(self, path: str) -> Optional[AttachmentID]:
        path = path.rsplit("/", 1)[-1]

        if path == Attachment.from_id(DefaultAvatarID):
            return DefaultAvatarID
        if path == Attachment.from_id(DefaultRoomID):
            return DefaultRoomID
        if path == Attachment.from_id(FaviconID):
            return FaviconID
        if path in _hash_to_id_lut:
            return _hash_to_id_lut[path]

        attachments = self.__data.attachment.get_attachments()
        for attachment in attachments:
            path = self._get_hashed_attachment_name(attachment.id)
            _hash_to_id_lut[path] = attachment.id

        return _hash_to_id_lut.get(path, None)

    def create_attachment(self, content_type: str) -> Optional[AttachmentID]:
        return self.__data.attachment.insert_attachment(self.__config.attachments.system, content_type)

    def destroy_attachment(self, attachmentid: AttachmentID) -> None:
        self.delete_attachment_data(attachmentid)
        self.__data.attachment.remove_attachment(attachmentid)

    def get_attachment_data(self, attachmentid: AttachmentID) -> Optional[Tuple[str, bytes]]:
        # Check for default images which aren't stored in the DB.
        if attachmentid == DefaultAvatarID or attachmentid == DefaultRoomID or attachmentid == FaviconID:
            if self.__config.attachments.system == "local":
                # Local storage, look up the storage directory and return that data.
                path = self._get_local_attachment_path(attachmentid)
                try:
                    with open(path, "rb") as bfp:
                        data = bfp.read()
                        enc = self.get_content_type(path)
                        return enc, data
                except FileNotFoundError:
                    return None
            else:
                # Unknown backend, throw.
                raise AttachmentServiceException("Unrecognized backend system!")

        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            return None

        if attachment.system == "local":
            # Local storage, look up the storage directory and return that data.
            path = self._get_local_attachment_path(attachmentid)
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
        # Check for default images which aren't stored in the DB.
        if attachmentid == DefaultAvatarID or attachmentid == DefaultRoomID or attachmentid == FaviconID:
            if self.__config.attachments.system == "local":
                # Local storage, look up the storage directory and return that data.
                path = self._get_local_attachment_path(attachmentid)
                with open(path, "wb") as bfp:
                    bfp.write(data)
            else:
                # Unknown backend, throw.
                raise AttachmentServiceException("Unrecognized backend system!")

            return

        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            return

        if attachment.system == "local":
            # Local storage, look up the storage directory and write the data.
            path = self._get_local_attachment_path(attachmentid)
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
            path = self._get_local_attachment_path(attachmentid)
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
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

        if action.action == ActionType.CHANGE_INFO:
            try:
                details = json.loads(action.details)
                if details.get("iconid"):
                    iconid = AttachmentID(int(details["iconid"]))
                    del details["iconid"]
                else:
                    iconid = None

                if iconid is None:
                    details["icon"] = self.get_attachment_url(DefaultRoomID)
                else:
                    details["icon"] = self.get_attachment_url(iconid)

                action.details = json.dumps(details)
            except json.decoder.JSONDecodeError:
                action.details = json.dumps({})
        elif action.action == ActionType.CHANGE_PROFILE:
            try:
                details = json.loads(action.details)
                if details.get("iconid"):
                    iconid = AttachmentID(int(details["iconid"]))
                    del details["iconid"]
                else:
                    iconid = None

                if iconid is None:
                    details["icon"] = self.get_attachment_url(DefaultAvatarID)
                else:
                    details["icon"] = self.get_attachment_url(iconid)

                action.details = json.dumps(details)
            except json.decoder.JSONDecodeError:
                action.details = json.dumps({})

        return action

    def resolve_chat_icon(self, room: Room) -> Room:
        if room.iconid is None:
            room.icon = self.get_attachment_url(DefaultAvatarID)
        else:
            room.icon = self.get_attachment_url(room.iconid)
        if room.deficonid is None:
            room.deficon = self.get_attachment_url(DefaultAvatarID)
        else:
            room.deficon = self.get_attachment_url(room.deficonid)
        return room

    def resolve_room_icon(self, room: Room) -> Room:
        if room.iconid is None:
            room.icon = self.get_attachment_url(DefaultRoomID)
        else:
            room.icon = self.get_attachment_url(room.iconid)
        if room.deficonid is None:
            room.deficon = self.get_attachment_url(DefaultRoomID)
        else:
            room.deficon = self.get_attachment_url(room.deficonid)
        return room

    def get_attachment_url(self, attachmentid: AttachmentID) -> str:
        prefix = self.__config.attachments.prefix
        if prefix[-1] == "/":
            prefix = prefix[:-1]
        return f"{prefix}/{self._get_hashed_attachment_name(attachmentid)}"
