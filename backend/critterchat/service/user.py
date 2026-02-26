from ..common import Time, represents_real_text
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
    RoomPurpose,
    DefaultAvatarID,
    DefaultRoomID,
    FaviconID,
    NewActionID,
    NewOccupantID,
    NewUserID,
    ActionID,
    AttachmentID,
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

    def migrate_legacy_names(self) -> None:
        """
        Check for any nicknames that somebody was able to set which do not follow our
        rules for nicknames, and remove the nickname, defaulting that user back to
        their username. This mostly entails exploits for blank names with unicode tricks.
        """

        # Don't check for whether this migration ran, we want it to run every restart.
        users = self.__data.user.get_users()
        for user in users:
            if user.nickname and not represents_real_text(user.nickname):
                user.nickname = ""
                self.__data.user.update_user(user)
                self.__notify_user_changed(user.id)

    def get_last_user_update(self) -> int | None:
        return self.__data.user.get_last_user_update()

    def get_settings(self, session: str, userid: UserID) -> UserSettings:
        settings = self.__data.user.get_settings(session)
        if settings:
            return settings

        settings = self.__data.user.get_any_settings(userid)
        if settings:
            return settings

        # For convenience/looks, look up the last room action for the rooms they're in
        # and place them into the room with the latest action.
        rooms = self.__data.room.get_joined_rooms(userid)
        rooms = sorted(rooms, key=lambda room: room.last_action_timestamp, reverse=True)
        roomid = rooms[0].id if rooms else None

        return UserSettings(
            userid=userid,
            roomid=roomid,
            info=None,
        )

    def update_settings(self, session: str, settings: UserSettings) -> None:
        self.__data.user.put_settings(session, settings)

    def get_preferences(self, userid: UserID) -> UserPreferences:
        prefs = self.__data.user.get_preferences(userid)
        if not prefs:
            prefs = UserPreferences.default(userid)

        notifs = self.__data.attachment.get_notifications(userid)
        prefs.notif_sounds = {key: self.__attachments.get_attachment_url(value.id) for key, value in notifs.items()}
        return prefs

    def update_preferences(
        self,
        userid: UserID,
        *,
        rooms_on_top: bool | None = None,
        combined_messages: bool | None = None,
        color_scheme: str | None = None,
        desktop_size: str | None = None,
        mobile_size: str | None = None,
        admin_controls: str | None = None,
        title_notifs: bool | None = None,
        mobile_audio_notifs: bool | None = None,
        audio_notifs: set[str] | None = None,
        notif_sounds: dict[str, AttachmentID] | None = None,
        notif_sounds_delete: set[str] | None = None,
    ) -> None:
        prefs = self.__data.user.get_preferences(userid)
        if not prefs:
            prefs = UserPreferences.default(userid)

        # First, update any changed booleans/flags/etc.
        if rooms_on_top is not None:
            prefs.rooms_on_top = rooms_on_top
        if combined_messages is not None:
            prefs.combined_messages = combined_messages
        if color_scheme is not None:
            prefs.color_scheme = color_scheme
        if desktop_size is not None:
            prefs.desktop_size = desktop_size
        if mobile_size is not None:
            prefs.mobile_size = mobile_size
        if admin_controls is not None:
            prefs.admin_controls = admin_controls
        if title_notifs is not None:
            prefs.title_notifs = title_notifs
        if mobile_audio_notifs is not None:
            prefs.mobile_audio_notifs = mobile_audio_notifs
        if audio_notifs is not None:
            try:
                prefs.audio_notifs = {UserNotification[an] for an in audio_notifs}
            except KeyError:
                pass

        # Now, handle uploading any new notification sounds.
        for alias, attachmentid in (notif_sounds or {}).items():
            try:
                actual = UserNotification[alias]
            except KeyError:
                continue

            # Ensure that the sound is actually valid and not something random.
            notificationdata = self.__data.attachment.lookup_attachment(attachmentid)
            if notificationdata is None:
                # Skip adding this notification, it's not valid.
                raise UserServiceException("Notification is not valid!")

            if notificationdata.content_type not in {"audio/mpeg"}:
                # Trying to sneak a bad attachment in.
                raise UserServiceException("Notification is not valid!")

            self.__data.attachment.set_notification(userid, str(actual.name), attachmentid)

        # Now, handle deleting any deleted notification sounds.
        for alias in notif_sounds_delete or {}:
            try:
                actual = UserNotification[alias]
            except KeyError:
                continue

            existing = self.__data.attachment.get_notification(userid, str(actual.name))
            if existing:
                self.__data.attachment.remove_notification(userid, str(actual.name))
                self.__attachments.delete_attachment_data(existing.id)
                self.__data.attachment.remove_attachment(existing.id)

        # Now, figure out what notifications should be enabled based on what
        # sounds are uploaded.
        notifs = self.__data.attachment.get_notifications(userid)
        actual_set: set[UserNotification] = set()
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

    def create_user(self, username: str, password: str) -> User:
        # First, try to create the actual account.
        user = self.__data.user.create_account(username, password)
        if not user:
            raise UserServiceException("Username already exists, please choose another!")

        # Check network settings and auto-activate user if the setting for this is enabled.
        if self.__config.account_registration.auto_approve:
            self.add_permission(user.id, UserPermission.ACTIVATED)
            user.permissions.add(UserPermission.ACTIVATED)

        # Finally, return the user that was just created.
        return user

    def lookup_user(self, userid: UserID) -> User | None:
        user = self.__data.user.get_user(userid)
        if user:
            self.__attachments.resolve_user_icon(user)
        return user

    def find_user(self, username: str) -> User | None:
        # Just try to find the user by username, returning that.
        user = self.__data.user.from_username(username)
        if user:
            self.__attachments.resolve_user_icon(user)
        return user

    def update_user(
        self,
        userid: UserID,
        name: str | None = None,
        about: str | None = None,
        icon: AttachmentID | None = None,
        icon_delete: bool = False,
    ) -> None:
        # Sanitize inputs.
        if icon == DefaultAvatarID or icon == DefaultRoomID or icon == FaviconID:
            icon = None
        if icon is not None:
            icondata = self.__data.attachment.lookup_attachment(icon)
            if icondata is None:
                # Skip adding this icon, it's not valid.
                raise UserServiceException("Updated avatar not valid!")

            if icondata.content_type not in AttachmentService.SUPPORTED_IMAGE_TYPES:
                # Trying to sneak a bad attachment in.
                raise UserServiceException("Updated avatar is not valid!")

        # Grab rooms the user is in so we can figure out which ones need updating.
        old_occupancy = self.__data.room.get_joined_room_occupants(userid)

        user = self.__data.user.get_user(userid)
        if user:
            changed = False
            old_icon = user.iconid

            # Always update name/about if it's set.
            if name is not None:
                changed = changed or (user.nickname != name)
                user.nickname = name
            if about is not None:
                changed = changed or (user.about != about)
                user.about = about

            # Allow updating icon, or deleting icon.
            if icon is not None:
                user.iconid = icon
            elif icon_delete:
                user.iconid = None

            # Ensure we don't store links to default icons.
            if user.iconid == DefaultAvatarID or user.iconid == DefaultRoomID or user.iconid == FaviconID:
                user.iconid = None
            if user.iconid != old_icon:
                changed = True

            if changed:
                self.__data.user.update_user(user)

        # Now, grab the occupants for the same user and write an action event for
        # every one that changed.
        self.__notify_user_changed(userid, old_occupancy)

    def change_user_password(self, userid: UserID, password: str) -> None:
        # Just ensure the user exists and then update the password.
        user = self.__data.user.get_user(userid)
        if not user:
            raise UserServiceException("User does not exist in the database!")

        # Now, update the password for the user.
        self.__data.user.update_password(user.id, password)

    def create_user_recovery(self, userid: UserID) -> str:
        # First, ensure the user existis so we can get the ID of the user.
        user = self.__data.user.get_user(userid)
        if not user:
            raise UserServiceException("User does not exist in the database!")

        # Now, generate and return a recovery string for the user.
        recovery = self.__data.user.create_recovery(user.id)
        url = f"{self.__config.base_url}/recover/{recovery}"
        while "//" in url:
            url = url.replace("//", "/")
        url = url.replace("http:/", "http://")
        url = url.replace("https:/", "https://")
        return url

    def create_user_invite(self, userid: UserID) -> str:
        if userid != NewUserID:
            # First, ensure the user existis so we can get the ID of the user doing
            # the inviting.
            user = self.__data.user.get_user(userid)
            if not user:
                raise UserServiceException("User does not exist in the database!")

        # Now, generate and return an invite string for the user.
        invite = self.__data.user.create_invite(userid)
        url = f"{self.__config.base_url}/register/{invite}"
        while "//" in url:
            url = url.replace("//", "/")
        url = url.replace("http:/", "http://")
        url = url.replace("https:/", "https://")
        return url

    def recover_user_password(self, username: str, recovery: str, password: str) -> User:
        # First, try to look up the user by the recovery string given.
        user = self.__data.user.from_recovery(recovery)
        if not user:
            raise UserServiceException("Unrecognized or expired recovery URL!")

        if user.username.lower() != username.lower():
            raise UserServiceException("Recovery URL is not for your account!")

        # Now, update the password since the checks passed.
        self.__data.user.update_password(user.id, password)

        # Finally, return that user.
        return user

    def __notify_user_changed(self, userid: UserID, old_occupancy: dict[RoomID, Occupant] | None = None) -> None:
        old_occupancy = old_occupancy or {}
        new_occupancy = self.__data.room.get_joined_room_occupants(userid)
        changes: dict[RoomID, Occupant] = {}

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
                details={"nickname": occupant.nickname, "iconid": occupant.iconid}
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
        self.__notify_users_updated(userid, permission)

    def remove_permission(self, userid: UserID, permission: UserPermission) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise UserServiceException("User does not exist to remove permission!")
        if permission in user.permissions:
            user.permissions.remove(permission)
        self.__data.user.update_user(user)
        self.__notify_users_updated(userid, permission)

    def __notify_users_updated(self, userid: UserID, permission: UserPermission) -> None:
        # Only want to notify on things that change actual user status in a room.
        if permission not in {UserPermission.ACTIVATED, UserPermission.ADMINISTRATOR}:
            return

        # Look up all rooms that this user is in and add an action to them notifying users changed.
        joinedrooms = self.__data.room.get_joined_rooms(userid)
        leftrooms = self.__data.room.get_left_rooms(userid)
        leftrooms = [r for r in leftrooms if r.purpose == RoomPurpose.DIRECT_MESSAGE]

        # Shouldn't happen, but let's not double-notify.
        seen: set[RoomID] = set()
        for room in [*joinedrooms, *leftrooms]:
            if room.id in seen:
                continue
            seen.add(room.id)

            occupant = Occupant(
                occupantid=NewOccupantID,
                userid=userid,
            )
            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.CHANGE_USERS,
                # For this action, the details will be filled in at look-up time.
                details={},
            )
            self.__data.room.insert_action(room.id, action)

    def mark_last_seen(self, userid: UserID, roomid: RoomID, actionid: ActionID) -> None:
        self.__data.user.mark_last_seen(userid, roomid, actionid)

    def get_last_seen_counts(self, userid: UserID) -> dict[RoomID, int]:
        lastseen = self.__data.user.get_last_seen_counts(userid)
        return {ls[0]: ls[1] for ls in lastseen}

    def get_last_seen_actions(self, userid: UserID) -> dict[RoomID, ActionID]:
        lastseen = self.__data.user.get_last_seen_actions(userid)
        return {ls[0]: ls[1] for ls in lastseen}
