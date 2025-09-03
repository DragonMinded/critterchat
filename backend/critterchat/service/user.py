import io
import json
import tempfile
from PIL import Image
from pydub import AudioSegment  # type: ignore
from typing import Dict, Optional, Set

from ..common import Time
from ..config import Config
from ..data import (
    Data,
    UserPreferences,
    UserSettings,
    UserPermission,
    UserNotification,
    User,
    Action,
    ActionType,
    DefaultAvatarID,
    NewActionID,
    ActionID,
    Occupant,
    RoomID,
    UserID,
)
from .attachment import AttachmentService


class UserServiceException(Exception):
    pass


class UserService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def get_settings(self, session: str, userid: UserID) -> UserSettings:
        settings = self.__data.user.get_settings(session)
        if settings:
            return settings

        settings = self.__data.user.get_any_settings(userid)
        if settings:
            return settings

        return UserSettings(
            userid=userid,
            roomid=None,
            info=None,
        )

    def update_settings(self, session: str, settings: UserSettings) -> None:
        self.__data.user.put_settings(session, settings)

    def get_preferences(self, userid: UserID) -> UserPreferences:
        prefs = self.__data.user.get_preferences(userid)
        if not prefs:
            prefs = UserPreferences(
                userid=userid,
                title_notifs=True,
                audio_notifs=set(),
            )

        notifs = self.__data.attachment.get_notifications(userid)
        prefs.notif_sounds = {key: self.__attachments.get_attachment_url(value.id) for key, value in notifs.items()}
        return prefs

    def update_preferences(
        self,
        userid: UserID,
        title_notifs: Optional[bool] = None,
        audio_notifs: Optional[Set[str]] = None,
        notif_sounds: Optional[Dict[str, bytes]] = None,
    ) -> None:
        prefs = self.__data.user.get_preferences(userid)
        if not prefs:
            prefs = UserPreferences(
                userid=userid,
                title_notifs=True,
                audio_notifs=set(),
            )

        # First, update any changed booleans/flags/etc.
        if title_notifs is not None:
            prefs.title_notifs = title_notifs
        if audio_notifs is not None:
            try:
                prefs.audio_notifs = {UserNotification[an] for an in audio_notifs}
            except KeyError:
                pass

        # Now, handle uploading any new notification sounds.
        for alias, data in (notif_sounds or {}).items():
            try:
                actual = UserNotification[alias]
            except KeyError:
                continue

            with tempfile.NamedTemporaryFile(delete_on_close=False) as fp1:
                fp1.write(data)
                fp1.close()

                segment = AudioSegment.from_file(fp1.name)

                with tempfile.NamedTemporaryFile(delete_on_close=False) as fp2:
                    fp2.close()

                    segment.export(fp2.name, format="mp3")

                    with open(fp2.name, "rb") as bfp:
                        actual_data = bfp.read()

                        attachmentid = self.__attachments.create_attachment("audio/mpeg")
                        if attachmentid is None:
                            raise UserServiceException("Could not insert new user notification sound!")
                        self.__attachments.put_attachment_data(attachmentid, actual_data)
                        self.__data.attachment.set_notification(userid, str(actual.name), attachmentid)

        # Now, figure out what notifications should be enabled based on what
        # sounds are uploaded.
        notifs = self.__data.attachment.get_notifications(userid)
        actual_set: Set[UserNotification] = set()
        for alias in notifs:
            try:
                actual_set.add(UserNotification[alias])
            except KeyError:
                continue
        prefs.audio_notifs = prefs.audio_notifs.intersection(actual_set)

        # And persist!
        self.__data.user.put_preferences(prefs)

    def has_updated_preferences(self, userid: UserID, last_checked: int) -> bool:
        return self.__data.user.has_updated_preferences(userid, last_checked)

    def lookup_user(self, userid: UserID) -> Optional[User]:
        user = self.__data.user.get_user(userid)
        if user:
            self.__attachments.resolve_user_icon(user)
        return user

    def create_user(self, username: str, password: str) -> User:
        # First, try to create the actual account.
        user = self.__data.user.create_account(username, password)
        if not user:
            raise UserServiceException("Username already exists, please choose another!")

        # TODO: Check network settings and auto-activate user if the setting for this is enabled.

        # Finally, return the user that was just created.
        return user

    def update_user(
        self,
        userid: UserID,
        name: Optional[str] = None,
        icon: Optional[bytes] = None,
    ) -> None:
        # Grab rooms the user is in so we can figure out which ones need updating.
        old_occupancy = self.__data.room.get_joined_room_occupants(userid)

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
                    raise UserServiceException("Invalid image size for user avatar")
                if width != height:
                    raise UserServiceException("User avatar image is not square")

                content_type = img.get_format_mimetype()
                if not content_type:
                    raise UserServiceException("User avatar image has no valid content type")

                attachmentid = self.__attachments.create_attachment(content_type)
                if attachmentid is None:
                    raise UserServiceException("Could not insert new user avatar!")
                self.__attachments.put_attachment_data(attachmentid, icon)

                changed = True
                user.iconid = attachmentid

            if user.iconid == DefaultAvatarID:
                user.iconid = None

            if changed:
                self.__data.user.update_user(user)

        # Now, grab the occupants for the same user and write an action event for
        # every one that changed.
        new_occupancy = self.__data.room.get_joined_room_occupants(userid)
        changes: Dict[RoomID, Occupant] = {}

        for roomid, occupant in new_occupancy.items():
            if roomid not in old_occupancy:
                changes[roomid] = occupant
                continue

            old = old_occupancy[roomid]
            if old.nickname != occupant.nickname or old.iconid != occupant.iconid:
                # Changed, notify this channel.
                changes[roomid] = occupant

        for roomid, occupant in changes.items():
            self.__attachments.resolve_occupant_icon(occupant)

            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.CHANGE_PROFILE,
                details=json.dumps({"nickname": occupant.nickname, "iconid": occupant.iconid})
            )
            self.__data.room.insert_action(roomid, action)

    def has_updated_user(self, userid: UserID, last_checked: int) -> bool:
        return self.__data.user.has_updated_user(userid, last_checked)

    def add_permission(self, userid: UserID, permission: UserPermission) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise UserServiceException("User does not exist to add permission!")
        user.permissions.add(permission)
        self.__data.user.update_user(user)

    def remove_permission(self, userid: UserID, permission: UserPermission) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise UserServiceException("User does not exist to remove permission!")
        if permission in user.permissions:
            user.permissions.remove(permission)
        self.__data.user.update_user(user)

    def mark_last_seen(self, userid: UserID, roomid: RoomID, actionid: ActionID) -> None:
        self.__data.user.mark_last_seen(userid, roomid, actionid)

    def get_last_seen_counts(self, userid: UserID) -> Dict[RoomID, int]:
        lastseen = self.__data.user.get_last_seen_counts(userid)
        return {ls[0]: ls[1] for ls in lastseen}

    def get_last_seen_actions(self, userid: UserID) -> Dict[RoomID, ActionID]:
        lastseen = self.__data.user.get_last_seen_actions(userid)
        return {ls[0]: ls[1] for ls in lastseen}
