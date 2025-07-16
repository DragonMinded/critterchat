import io
from PIL import Image
from typing import Dict, Optional

from ..config import Config
from ..data import Data, UserSettings, User, DefaultAvatarID, ActionID, RoomID, UserID
from .attachment import AttachmentService


class UserServiceException(Exception):
    pass


class UserService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def get_settings(self, userid: UserID) -> UserSettings:
        settings = self.__data.user.get_settings(userid)
        if settings:
            return settings

        return UserSettings(
            userid=userid,
            roomid=None,
            info=None,
        )

    def update_settings(self, userid: UserID, settings: UserSettings) -> None:
        if userid != settings.id:
            raise UserServiceException("Invaid User ID in settings bundle!")

        self.__data.user.put_settings(userid, settings)

    def lookup_user(self, userid: UserID) -> Optional[User]:
        user = self.__data.user.get_user(userid)
        if user:
            self.__attachments.resolve_user_icon(user)
        return user

    def update_user(
        self,
        userid: UserID,
        name: Optional[str] = None,
        icon: Optional[bytes] = None,
    ) -> None:
        user = self.__data.user.get_user(userid)
        if user:
            changed = False
            if name is not None:
                user.nickname = name
                changed = True
            if icon is not None:
                # Need to store this as a new attachment, and then get back the ID.
                img = Image.open(io.BytesIO(icon))
                width, height = img.size

                if width > AttachmentService.MAX_ICON_WIDTH or height > AttachmentService.MAX_ICON_HEIGHT:
                    raise UserServiceException("Invalid image size for user icon")
                if width != height:
                    raise UserServiceException("User icon image is not square")

                content_type = img.get_format_mimetype()
                if not content_type:
                    raise UserServiceException("User icon image has no valid content type")

                attachmentid = self.__attachments.create_attachment(content_type)
                if attachmentid is None:
                    raise UserServiceException("Could not insert new user icon!")
                self.__attachments.put_attachment_data(attachmentid, icon)

                changed = True
                user.iconid = attachmentid

            if user.iconid == DefaultAvatarID:
                user.iconid = None

            if changed:
                self.__data.user.update_user(user)

    def mark_last_seen(self, userid: UserID, roomid: RoomID, actionid: ActionID) -> None:
        self.__data.user.mark_last_seen(userid, roomid, actionid)

    def get_last_seen_counts(self, userid: UserID) -> Dict[RoomID, int]:
        lastseen = self.__data.user.get_last_seen_counts(userid)
        return {ls[0]: ls[1] for ls in lastseen}
