from enum import IntEnum, StrEnum
from typing import NewType, cast

from ..config import Config


UserID = NewType("UserID", int)
RoomID = NewType("RoomID", int)
OccupantID = NewType("OccupantID", int)
ActionID = NewType("ActionID", int)
AttachmentID = NewType("AttachmentID", int)
MastodonInstanceID = NewType("MastodonInstanceID", int)


NewUserID = UserID(-1)
NewRoomID = RoomID(-1)
NewOccupantID = OccupantID(-1)
NewMastodonInstanceID = MastodonInstanceID(-1)
NewActionID = ActionID(-1)
NewAttachmentID = AttachmentID(-1)
DefaultAvatarID = AttachmentID(-100)
DefaultRoomID = AttachmentID(-200)
FaviconID = AttachmentID(-300)


class Migration(StrEnum):
    HASHED_ATTACHMENTS = "hashed_attachments"
    ATTACHMENT_EXTENSIONS = "attachment_extensions"
    IMAGE_DIMENSIONS = "image_dimensions"


class UserPermission(IntEnum):
    ACTIVATED = 0x1
    WELCOMED = 0x2
    ADMINISTRATOR = 0x4


class User:
    def __init__(
        self,
        userid: UserID,
        username: str,
        permissions: set[UserPermission],
        nickname: str,
        about: str,
        iconid: AttachmentID | None,
    ) -> None:
        self.id = userid
        self.username = username
        self.about = about
        self.permissions = permissions
        self.nickname = nickname
        self.iconid = iconid
        self.icon: str | None = None

        # Only set when this user is looked up through message service based on an OID.
        self.occupantid: OccupantID | None = None
        self.moderator: bool | None = None
        self.muted: bool | None = None

    def to_dict(self, *, config: Config | None = None, admin: bool = False) -> dict[str, object]:
        retval: dict[str, object] = {
            "id": User.from_id(self.id),
            "username": self.username,
            "nickname": self.nickname,
            "about": self.about,
            "icon": self.icon,
        }

        if self.occupantid:
            retval["occupantid"] = Occupant.from_id(self.occupantid)
        if self.moderator is not None:
            retval["moderator"] = self.moderator
        if self.muted is not None:
            retval["muted"] = self.muted

        if config:
            retval["full_username"] = f"@{self.username}@{config.account_base}"

        if admin:
            retval["permissions"] = [p.name for p in self.permissions]

        return retval

    @staticmethod
    def from_id(userid: UserID) -> str:
        return f"u{userid}"

    @staticmethod
    def to_id(idstr: str) -> UserID | None:
        if idstr[0] != 'u':
            return None

        try:
            return UserID(int(idstr[1:]))
        except ValueError:
            return None


class UserSettings:
    def __init__(self, userid: UserID, roomid: RoomID | None, info: str | None) -> None:
        self.userid = userid
        self.roomid = roomid
        self.info = info

    def to_dict(self) -> dict[str, object]:
        return {
            "roomid": Room.from_id(self.roomid) if self.roomid is not None else None,
            "info": self.info if self.info else "hidden",
        }

    @staticmethod
    def from_dict(userid: UserID, values: dict[str, object]) -> "UserSettings":
        room = values.get("roomid")
        roomid = Room.to_id(str(room)) if room is not None else None
        info: str = str(values['info']) if values.get("info") else "hidden"

        return UserSettings(
            userid=userid,
            roomid=roomid,
            info=info,
        )


class UserNotification(IntEnum):
    # You sent a chat to a public room.
    CHAT_SENT = 0x001
    # You received a chat in a public room.
    CHAT_RECEIVED = 0x002
    # You sent a message in a private room.
    MESSAGE_SENT = 0x004
    # You received a message in a private room.
    MESSAGE_RECEIVED = 0x008
    # You were mentioned by username in a public/private room.
    MENTIONED = 0x010
    # A user joined a room you're in.
    USER_JOINED = 0x020
    # A user left a room you're in.
    USER_LEFT = 0x040
    # A user reacted to a message in a room you're in.
    USER_REACTED = 0x080
    # A user reacted to a message you wrote in a room you're in.
    REACTION_RECEIVED = 0x100


class UserPreferences:
    def __init__(
        self,
        userid: UserID,
        *,
        rooms_on_top: bool,
        combined_messages: bool,
        color_scheme: str,
        desktop_size: str,
        mobile_size: str,
        admin_controls: str,
        title_notifs: bool,
        mobile_audio_notifs: bool,
        audio_notifs: set[UserNotification],
    ) -> None:
        self.userid = userid
        self.rooms_on_top = rooms_on_top
        self.combined_messages = combined_messages
        self.color_scheme = color_scheme
        self.desktop_size = desktop_size
        self.mobile_size = mobile_size
        self.admin_controls = admin_controls
        self.title_notifs = title_notifs
        self.mobile_audio_notifs = mobile_audio_notifs
        self.audio_notifs = audio_notifs
        self.notif_sounds: dict[str, str] = {}

    def to_dict(self) -> dict[str, object]:
        return {
            "rooms_on_top": self.rooms_on_top,
            "combined_messages": self.combined_messages,
            "color_scheme": self.color_scheme,
            "desktop_size": self.desktop_size,
            "mobile_size": self.mobile_size,
            "admin_controls": self.admin_controls,
            "title_notifs": self.title_notifs,
            "mobile_audio_notifs": self.mobile_audio_notifs,
            "audio_notifs": [str(an.name) for an in self.audio_notifs],
            "notif_sounds": self.notif_sounds,
        }

    @staticmethod
    def default(userid: UserID) -> "UserPreferences":
        return UserPreferences(
            userid=userid,
            rooms_on_top=False,
            combined_messages=False,
            color_scheme="system",
            desktop_size="normal",
            mobile_size="normal",
            admin_controls="visible",
            title_notifs=True,
            mobile_audio_notifs=False,
            audio_notifs=set(),
        )


class MetadataType(StrEnum):
    WIDTH = 'width'
    HEIGHT = 'height'
    ALT_TEXT = 'alt_text'
    SENSITIVE = 'sensitive'


class Attachment:
    def __init__(
        self,
        attachmentid: AttachmentID,
        uri: str,
        mimetype: str,
        metadata: dict[MetadataType, object],
    ) -> None:
        self.id = attachmentid
        self.uri = uri
        self.mimetype = mimetype
        self.metadata = metadata

    def clone(self) -> "Attachment":
        return Attachment(
            self.id,
            self.uri,
            self.mimetype,
            {**self.metadata},
        )

    def to_dict(self) -> dict[str, object]:
        return {
            # Intentionally don't include ID here because doing so along with the URI could allow
            # an attacker to reverse the URI hash and enumerate attachments by ID. This could
            # expose private attachments to URI guessing.
            "uri": self.uri,
            "mimetype": self.mimetype,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_id(attachmentid: AttachmentID) -> str:
        if attachmentid == DefaultAvatarID:
            return "defavi"
        if attachmentid == DefaultRoomID:
            return "defroom"
        if attachmentid == FaviconID:
            return "deficon"
        return f"d{attachmentid}"

    @staticmethod
    def to_id(idstr: str) -> AttachmentID | None:
        if idstr == "defavi":
            return DefaultAvatarID
        if idstr == "defroom":
            return DefaultRoomID
        if idstr == "deficon":
            return FaviconID

        if idstr[0] != 'd':
            return None

        try:
            return AttachmentID(int(idstr[1:]))
        except ValueError:
            return None


class RoomPurpose(StrEnum):
    ROOM = 'room'
    CHAT = 'chat'
    DIRECT_MESSAGE = 'dm'


class Room:
    def __init__(
        self,
        roomid: RoomID,
        name: str,
        topic: str,
        purpose: RoomPurpose,
        moderated: bool,
        iconid: AttachmentID | None,
        deficonid: AttachmentID | None,
        oldest_action: ActionID | None = None,
        newest_action: ActionID | None = None,
        last_action_timestamp: int = 0,
    ) -> None:
        self.id = roomid
        self.name = name or ""
        self.customname = self.name
        self.topic = topic or ""
        self.purpose = purpose
        self.moderated = moderated
        self.oldest_action = oldest_action
        self.newest_action = newest_action
        self.last_action_timestamp = last_action_timestamp
        self.iconid = iconid
        self.deficonid = deficonid

        # Resolved based on the purpose of the room itself.
        self.public = purpose == RoomPurpose.ROOM

        # Resolved only after lookup by attachment system.
        self.icon: str | None = None
        self.deficon: str | None = None

        # Resolved only after lookup by message/search system, not sent to clients.
        self.occupants: list[Occupant] = []

    def to_dict(self) -> dict[str, object]:
        return {
            "id": Room.from_id(self.id),
            "type": self.purpose,
            "name": self.name,
            "customname": self.customname,
            "topic": self.topic,
            "public": self.public,
            "moderated": self.moderated,
            "oldest_action": Action.from_id(self.oldest_action) if self.oldest_action else None,
            "newest_action": Action.from_id(self.newest_action) if self.newest_action else None,
            "last_action_timestamp": self.last_action_timestamp,
            "icon": self.icon,
            "deficon": self.deficon,
        }

    @staticmethod
    def from_id(roomid: RoomID) -> str:
        return f"r{roomid}"

    @staticmethod
    def to_id(idstr: str) -> RoomID | None:
        if idstr[0] != 'r':
            return None

        try:
            return RoomID(int(idstr[1:]))
        except ValueError:
            return None


class RoomSearchResult:
    def __init__(
        self,
        name: str,
        handle: str | None,
        purpose: RoomPurpose,
        joined: bool,
        roomid: RoomID | None,
        userid: UserID | None,
        icon: str,
    ) -> None:
        self.name = name
        self.handle = handle
        self.purpose = purpose
        self.joined = joined
        self.roomid = roomid
        self.userid = userid
        self.icon = icon

        # Resolved from room type.
        self.public = purpose == RoomPurpose.ROOM

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "handle": self.handle,
            "type": self.purpose,
            "icon": self.icon,
            "public": self.public,
            "joined": self.joined,
            "roomid": Room.from_id(self.roomid) if self.roomid else None,
            "userid": User.from_id(self.userid) if self.userid else None,
        }


class Occupant:
    def __init__(
        self,
        occupantid: OccupantID,
        userid: UserID,
        username: str = "",
        nickname: str = "",
        iconid: AttachmentID | None = None,
        inactive: bool = False,
        moderator: bool = False,
        muted: bool = False,
    ) -> None:
        self.id = occupantid
        self.userid = userid
        self.username = username
        self.nickname = nickname
        self.inactive = inactive
        self.moderator = moderator
        self.muted = muted
        self.iconid = iconid
        self.icon: str | None = None

    def clone(self) -> "Occupant":
        o = Occupant(
            occupantid=self.id,
            userid=self.userid,
            username=self.username,
            nickname=self.nickname,
            iconid=self.iconid,
            inactive=self.inactive,
            moderator=self.moderator,
            muted=self.muted,
        )
        o.icon = self.icon
        return o

    def to_dict(self) -> dict[str, object]:
        return {
            "id": Occupant.from_id(self.id),
            "userid": User.from_id(self.userid),
            "username": self.username,
            "nickname": self.nickname,
            "inactive": self.inactive,
            "moderator": self.moderator,
            "muted": self.muted,
            "icon": self.icon,
        }

    @staticmethod
    def from_id(occupantid: OccupantID) -> str:
        return f"o{occupantid}"

    @staticmethod
    def to_id(idstr: str) -> OccupantID | None:
        if idstr[0] != 'o':
            return None

        try:
            return OccupantID(int(idstr[1:]))
        except ValueError:
            return None


class ActionType(StrEnum):
    MESSAGE = 'message'
    JOIN = 'join'
    LEAVE = 'leave'
    CHANGE_INFO = 'change_info'
    CHANGE_PROFILE = 'change_profile'
    CHANGE_USERS = 'change_users'
    CHANGE_MESSAGE = 'change_message'

    @staticmethod
    def unread_types() -> set["ActionType"]:
        # Type of actions that matter to unread counts and badges.
        return {
            ActionType.MESSAGE,
            ActionType.JOIN,
            ActionType.LEAVE,
            ActionType.CHANGE_INFO,
        }

    @staticmethod
    def unread_dm_types() -> set["ActionType"]:
        # Type of actions that matter specifically to DM unread counts and badges.
        return {
            ActionType.MESSAGE,
            ActionType.CHANGE_INFO,
        }

    @staticmethod
    def update_types() -> set["ActionType"]:
        # Type of actions that matter for delivering update notifications to clients.
        return {
            ActionType.MESSAGE,
            ActionType.JOIN,
            ActionType.LEAVE,
            ActionType.CHANGE_INFO,
            ActionType.CHANGE_PROFILE,
            ActionType.CHANGE_USERS,
            ActionType.CHANGE_MESSAGE,
        }


class Action:
    def __init__(
        self,
        actionid: ActionID,
        timestamp: int,
        occupant: Occupant | None,
        action: ActionType,
        details: dict[str, object],
        attachments: list[Attachment] = [],
    ) -> None:
        self.id = actionid
        self.timestamp = timestamp
        self.action = action
        self.details = details

        # Can be None, but only for specific action types. Right now that's just CHANGE_INFO
        # so that room info can be updated from the CLI.
        self.occupant = occupant

        # Only ever populated for message type.
        self.attachments = attachments

    def clone(self) -> "Action":
        return Action(
            self.id,
            self.timestamp,
            self.occupant.clone() if self.occupant else None,
            self.action,
            {**self.details},
            [a.clone() for a in self.attachments],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": Action.from_id(self.id),
            "order": self.id,
            "timestamp": self.timestamp,
            "occupant": self.occupant.to_dict() if self.occupant else None,
            "action": self.action,
            "details": self._get_details(),
            "attachments": [a.to_dict() for a in self.attachments],
        }

    def _get_details(self) -> dict[str, object]:
        if self.action == ActionType.CHANGE_MESSAGE:
            details = {**self.details}
            details["actionid"] = Action.from_id(cast(ActionID, details["actionid"]))
            return details

        if self.action == ActionType.MESSAGE:
            details = {**self.details}
            reactions = cast(dict[str, list[OccupantID]], details.get("reactions", {}))
            converted = {}

            for reaction, occupants in reactions.items():
                converted[reaction] = [Occupant.from_id(o) for o in occupants]
            details["reactions"] = converted

            return details

        return self.details

    @staticmethod
    def from_id(actionid: ActionID) -> str:
        return f"a{actionid}"

    @staticmethod
    def to_id(idstr: str) -> ActionID | None:
        if idstr[0] != 'a':
            return None

        try:
            return ActionID(int(idstr[1:]))
        except ValueError:
            return None


class Emote:
    def __init__(self, uri: str, dimensions: tuple[int, int]) -> None:
        self.uri = uri
        self.dimensions = dimensions

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "dimensions": list(self.dimensions),
        }


class MastodonInstance:
    def __init__(self, instanceid: MastodonInstanceID, base_url: str, client_id: str, client_secret: str) -> None:
        self.id = instanceid
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_token: str | None = None


class MastodonProfile:
    def __init__(self, instance_url: str, username: str, nickname: str, avatar: str, note: str) -> None:
        self.instance_url = instance_url
        self.username = username
        self.nickname = nickname
        self.avatar = avatar
        self.note = note
