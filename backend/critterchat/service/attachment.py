import io
import hashlib
import json
import mimetypes
import os
from PIL import Image, ImageOps
from typing import Dict, Final, Optional, Tuple

from ..config import Config
from ..data import (
    Data,
    Attachment,
    Action,
    ActionType,
    Migration,
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
_id_to_hash_lut: Dict[AttachmentID, str] = {}


class AttachmentService:
    MAX_ICON_WIDTH: Final[int] = 512
    MAX_ICON_HEIGHT: Final[int] = 512
    SUPPORTED_IMAGE_TYPES = {"image/apng", "image/gif", "image/jpeg", "image/png", "image/webp"}

    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data

    def get_content_type(self, filename: str) -> str:
        try:
            return mimetypes.types_map[os.path.splitext(filename.lower())[1]]
        except Exception:
            return "application/octet-stream"

    def _get_ext_from_content_type(self, content_type: str) -> str:
        content_type = content_type.lower()
        return {
            "audio/mpeg": ".mp3",
            "image/apng": ".apng",
            "image/gif": ".gif",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(content_type, "")

    def _get_hashed_attachment_name(self, aid: AttachmentID, content_type: str, original_filename: Optional[str]) -> str:
        # Default attachments don't get extensions.
        if aid in {DefaultAvatarID, DefaultRoomID, FaviconID}:
            return Attachment.from_id(aid)

        # Extensions match based on original filename if present, and then based on content type.
        if original_filename and "." in original_filename:
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower()
        else:
            ext = self._get_ext_from_content_type(content_type)

        hashkey = self.__config.attachments.attachment_key
        inval = f"{hashkey}-{Attachment.from_id(aid)}"
        hashval = hashlib.shake_256(inval.encode('utf-8')).hexdigest(20)
        return f"{hashval}{ext}"

    def _get_local_attachment_path(self, aid: AttachmentID, content_type: str, original_filename: Optional[str]) -> str:
        directory = self.__config.attachments.directory
        if not directory:
            raise AttachmentServiceException("Cannot find directory for local attachment storage!")

        return os.path.join(directory, self._get_hashed_attachment_name(aid, content_type, original_filename))

    def create_default_attachments(self) -> None:
        for aid, default in [
            (DefaultAvatarID, default_avatar),
            (DefaultRoomID, default_room),
            (FaviconID, default_icon),
        ]:
            if self.__config.attachments.system == "local":
                # Local storage, copy the system default into the attachment directory if needed.
                content_type = self.get_content_type(default)
                path = self._get_local_attachment_path(aid, content_type, None)
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
            def _get_prehashed_local_attachment_path(aid: AttachmentID) -> str:
                directory = self.__config.attachments.directory
                if not directory:
                    raise AttachmentServiceException("Cannot find directory for local attachment storage!")

                return os.path.join(directory, Attachment.from_id(aid))

            def _get_legacy_hashed_attachment_name(aid: AttachmentID) -> str:
                if aid in {DefaultAvatarID, DefaultRoomID, FaviconID}:
                    return Attachment.from_id(aid)

                hashkey = self.__config.attachments.attachment_key
                inval = f"{hashkey}-{Attachment.from_id(aid)}"
                return hashlib.shake_256(inval.encode('utf-8')).hexdigest(20)

            def _get_legacy_local_attachment_path(aid: AttachmentID) -> str:
                directory = self.__config.attachments.directory
                if not directory:
                    raise AttachmentServiceException("Cannot find directory for local attachment storage!")

                return os.path.join(directory, _get_legacy_hashed_attachment_name(aid))

            # Look up which of these we've done since they're expensive, skipping the work if not needed.
            finished_migrations = self.__data.migration.get_migrations()

            if (
                Migration.HASHED_ATTACHMENTS in finished_migrations and
                Migration.ATTACHMENT_EXTENSIONS in finished_migrations and
                Migration.IMAGE_DIMENSIONS in finished_migrations
            ):
                # We've done all the migrations, so don't bother looking up attachments.
                return

            # We need all known attachments in the system for both migrations below.
            attachments = self.__data.attachment.get_attachments()

            if Migration.HASHED_ATTACHMENTS not in finished_migrations:
                # First, we need to attempt to migrate from pre-hashed to hashed.
                for attachment in attachments:
                    # Local storage, copy the system default into the attachment directory if needed.
                    oldpath = _get_prehashed_local_attachment_path(attachment.id)
                    path = _get_legacy_local_attachment_path(attachment.id)
                    if (not os.path.isfile(path)) and os.path.isfile(oldpath):
                        with open(oldpath, "rb") as bfp1:
                            data = bfp1.read()
                        with open(path, "wb") as bfp2:
                            bfp2.write(data)
                        os.remove(oldpath)

                # Mark that we did this migration so we never run it again.
                self.__data.migration.flag_migrated(Migration.HASHED_ATTACHMENTS)

            if Migration.ATTACHMENT_EXTENSIONS not in finished_migrations:
                # Next, we need to attempt to migrate from pre-extension to extension.
                for attachment in attachments:
                    # Local storage, copy the system default into the attachment directory if needed.
                    oldpath = _get_legacy_local_attachment_path(attachment.id)
                    path = self._get_local_attachment_path(attachment.id, attachment.content_type, attachment.original_filename)
                    if path == oldpath:
                        # This can happen for files we don't have an original filename for and we don't
                        # have a matching extension for the mimetype (like application/octet-stream).
                        continue

                    if (not os.path.isfile(path)) and os.path.isfile(oldpath):
                        with open(oldpath, "rb") as bfp1:
                            data = bfp1.read()
                        with open(path, "wb") as bfp2:
                            bfp2.write(data)
                        os.remove(oldpath)

                # Mark that we did this migration so we never run it again.
                self.__data.migration.flag_migrated(Migration.ATTACHMENT_EXTENSIONS)

            if Migration.IMAGE_DIMENSIONS not in finished_migrations:
                # Now, we need to load all attachments that don't have dimensions and
                # cache the dimensions for those attachments.
                for attachment in attachments:
                    if attachment.content_type not in AttachmentService.SUPPORTED_IMAGE_TYPES:
                        # We're not concerned with this.
                        continue

                    if 'width' in attachment.metadata and 'height' in attachment.metadata:
                        # We already have dimensions on this.
                        continue

                    content_type_and_data = self.get_attachment_data(attachment.id)
                    if content_type_and_data:
                        _, data = content_type_and_data

                        try:
                            img = Image.open(io.BytesIO(data))
                        except Exception:
                            raise AttachmentServiceException(f"Unsupported image provided for {attachment.id}.")

                        transposed = ImageOps.exif_transpose(img)
                        width, height = transposed.size
                        self.__data.attachment.update_attachment_metadata(attachment.id, {'width': width, 'height': height})

                # Mark that we did this migration so we never run it again.
                self.__data.migration.flag_migrated(Migration.IMAGE_DIMENSIONS)

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
            calculated = self._get_hashed_attachment_name(attachment.id, attachment.content_type, attachment.original_filename)
            _hash_to_id_lut[calculated] = attachment.id
            _id_to_hash_lut[attachment.id] = calculated

        return _hash_to_id_lut.get(path, None)

    def create_attachment(
        self,
        content_type: str,
        original_filename: Optional[str],
        metadata: Dict[str, object],
    ) -> Optional[AttachmentID]:
        return self.__data.attachment.insert_attachment(
            self.__config.attachments.system,
            content_type,
            original_filename,
            metadata,
        )

    def destroy_attachment(self, attachmentid: AttachmentID) -> None:
        self.delete_attachment_data(attachmentid)
        self.__data.attachment.remove_attachment(attachmentid)

    def get_attachment_data(self, attachmentid: AttachmentID) -> Optional[Tuple[str, bytes]]:
        # Check for default images which aren't stored in the DB.
        if attachmentid == DefaultAvatarID or attachmentid == DefaultRoomID or attachmentid == FaviconID:
            if self.__config.attachments.system == "local":
                # Local storage, look up the storage directory and return that data.
                path = self._get_local_attachment_path(attachmentid, "application/octet-stream", None)
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
            path = self._get_local_attachment_path(attachment.id, attachment.content_type, attachment.original_filename)
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
                path = self._get_local_attachment_path(attachmentid, "application/octet-stream", None)
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
            path = self._get_local_attachment_path(attachment.id, attachment.content_type, attachment.original_filename)
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
            path = self._get_local_attachment_path(attachment.id, attachment.content_type, attachment.original_filename)
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

    def _get_attachment_name(self, attachmentid: AttachmentID) -> str:
        if attachmentid in _id_to_hash_lut:
            return _id_to_hash_lut[attachmentid]

        if attachmentid in {DefaultAvatarID, DefaultRoomID, FaviconID}:
            _id_to_hash_lut[attachmentid] = self._get_hashed_attachment_name(attachmentid, 'application/octet-stream', None)
            return _id_to_hash_lut[attachmentid]

        attachment = self.__data.attachment.lookup_attachment(attachmentid)
        if not attachment:
            # We can't find the attachment, so assume that it has no extension and try that.
            _id_to_hash_lut[attachmentid] = self._get_hashed_attachment_name(attachmentid, 'application/octet-stream', None)
            return _id_to_hash_lut[attachmentid]

        _id_to_hash_lut[attachmentid] = self._get_hashed_attachment_name(attachment.id, attachment.content_type, attachment.original_filename)
        return _id_to_hash_lut[attachmentid]

    def get_attachment_url(self, attachmentid: AttachmentID) -> str:
        prefix = self.__config.attachments.prefix
        if prefix[-1] == "/":
            prefix = prefix[:-1]

        return f"{prefix}/{self._get_attachment_name(attachmentid)}"
