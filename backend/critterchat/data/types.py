from enum import IntEnum, StrEnum
from typing import Dict, NewType, Optional, Set


UserID = NewType("UserID", int)
RoomID = NewType("RoomID", int)
OccupantID = NewType("OccupantID", int)
ActionID = NewType("ActionID", int)
AttachmentID = NewType("AttachmentID", int)


NewUserID = UserID(-1)
NewRoomID = RoomID(-1)
NewOccupantID = OccupantID(-1)
NewActionID = ActionID(-1)
NewAttachmentID = AttachmentID(-1)
DefaultAvatarID = AttachmentID(-100)
DefaultRoomID = AttachmentID(-200)


class UserPermission(IntEnum):
    ACTIVATED = 0x1
    WELCOMED = 0x2


class User:
    def __init__(self, userid: UserID, username: str, permissions: Set[UserPermission], nickname: str, iconid: Optional[AttachmentID]) -> None:
        self.id = userid
        self.username = username
        self.permissions = permissions
        self.nickname = nickname
        self.iconid = iconid
        self.icon: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": User.from_id(self.id),
            "username": self.username,
            "nickname": self.nickname,
            "icon": self.icon,
        }

    @staticmethod
    def from_id(userid: UserID) -> str:
        return f"u{userid}"

    @staticmethod
    def to_id(idstr: str) -> Optional[UserID]:
        if idstr[0] != 'u':
            return None

        try:
            return UserID(int(idstr[1:]))
        except ValueError:
            return None


class UserSettings:
    def __init__(self, userid: UserID, roomid: Optional[RoomID], info: Optional[str]) -> None:
        self.userid = userid
        self.roomid = roomid
        self.info = info

    def to_dict(self) -> Dict[str, object]:
        return {
            "roomid": Room.from_id(self.roomid) if self.roomid is not None else None,
            "info": self.info if self.info else "hidden",
        }

    @staticmethod
    def from_dict(userid: UserID, values: Dict[str, object]) -> "UserSettings":
        room = values.get("roomid")
        roomid = Room.to_id(str(room)) if room is not None else None
        info: str = str(values['info']) if values.get("info") else "hidden"

        return UserSettings(
            userid=userid,
            roomid=roomid,
            info=info,
        )


class UserNotification(IntEnum):
    CHAT_SENT = 0x1
    CHAT_RECEIVED = 0x2
    MESSAGE_SENT = 0x4
    MESSAGE_RECEIVED = 0x8
    MENTIONED = 0x10
    USER_JOINED = 0x20
    USER_LEFT = 0x40


class UserPreferences:
    def __init__(self, userid: UserID, *, rooms_on_top: bool, title_notifs: bool, mobile_audio_notifs: bool, audio_notifs: Set[UserNotification]) -> None:
        self.userid = userid
        self.rooms_on_top = rooms_on_top
        self.title_notifs = title_notifs
        self.mobile_audio_notifs = mobile_audio_notifs
        self.audio_notifs = audio_notifs
        self.notif_sounds: Dict[str, str] = {}

    def to_dict(self) -> Dict[str, object]:
        return {
            "rooms_on_top": self.rooms_on_top,
            "title_notifs": self.title_notifs,
            "mobile_audio_notifs": self.mobile_audio_notifs,
            "audio_notifs": [str(an.name) for an in self.audio_notifs],
            "notif_sounds": self.notif_sounds,
        }


class Attachment:
    def __init__(self, attachmentid: AttachmentID, uri: str, mimetype: str) -> None:
        self.id = attachmentid
        self.uri = uri
        self.mimetype = mimetype

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Attachment.from_id(self.id),
            "uri": self.uri,
            "mimetype": self.mimetype,
        }

    @staticmethod
    def from_id(attachmentid: AttachmentID) -> str:
        if attachmentid == DefaultAvatarID:
            return "defavi"
        if attachmentid == DefaultRoomID:
            return "defroom"
        return f"d{attachmentid}"

    @staticmethod
    def to_id(idstr: str) -> Optional[AttachmentID]:
        if idstr == "defavi":
            return DefaultAvatarID
        if idstr == "defroom":
            return DefaultRoomID

        if idstr[0] != 'd':
            return None

        try:
            return AttachmentID(int(idstr[1:]))
        except ValueError:
            return None


class RoomType(StrEnum):
    UNKNOWN = 'unknown'
    CHAT = 'chat'
    ROOM = 'room'


class Room:
    def __init__(
        self,
        roomid: RoomID,
        name: str,
        topic: str,
        public: bool,
        iconid: Optional[AttachmentID],
        deficonid: Optional[AttachmentID],
        oldest_action: Optional[ActionID] = None,
        last_action: int = 0,
    ) -> None:
        self.id = roomid
        self.type = RoomType.UNKNOWN
        self.name = name or ""
        self.customname = self.name
        self.topic = topic or ""
        self.public = public
        self.oldest_action = oldest_action
        self.last_action = last_action
        self.iconid = iconid
        self.deficonid = deficonid
        self.icon: Optional[str] = None
        self.deficon: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Room.from_id(self.id),
            "type": self.type,
            "name": self.name,
            "customname": self.customname,
            "topic": self.topic,
            "public": self.public,
            "oldest_action": Action.from_id(self.oldest_action) if self.oldest_action else None,
            "last_action": self.last_action,
            "icon": self.icon,
            "deficon": self.deficon,
        }

    @staticmethod
    def from_id(roomid: RoomID) -> str:
        return f"r{roomid}"

    @staticmethod
    def to_id(idstr: str) -> Optional[RoomID]:
        if idstr[0] != 'r':
            return None

        try:
            return RoomID(int(idstr[1:]))
        except ValueError:
            return None


class RoomSearchResult:
    def __init__(
        self, name: str, joined: bool, public: bool, roomid: Optional[RoomID], userid: Optional[UserID], icon: str,
    ) -> None:
        self.name = name
        self.joined = joined
        self.roomid = roomid
        self.userid = userid
        self.public = public
        self.icon = icon

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
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
        iconid: Optional[AttachmentID] = None,
        inactive: bool = False,
    ) -> None:
        self.id = occupantid
        self.userid = userid
        self.username = username
        self.nickname = nickname
        self.inactive = inactive
        self.iconid = iconid
        self.icon: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Occupant.from_id(self.id),
            "userid": User.from_id(self.userid),
            "username": self.username,
            "nickname": self.nickname,
            "inactive": self.inactive,
            "icon": self.icon,
        }

    @staticmethod
    def from_id(occupantid: OccupantID) -> str:
        return f"o{occupantid}"

    @staticmethod
    def to_id(idstr: str) -> Optional[OccupantID]:
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

    @staticmethod
    def unread_types() -> Set["ActionType"]:
        return {
            ActionType.MESSAGE,
            ActionType.JOIN,
            ActionType.LEAVE,
            ActionType.CHANGE_INFO,
        }

    @staticmethod
    def update_types() -> Set["ActionType"]:
        return {
            ActionType.MESSAGE,
            ActionType.JOIN,
            ActionType.LEAVE,
            ActionType.CHANGE_INFO,
            ActionType.CHANGE_PROFILE,
        }


class Action:
    def __init__(self, actionid: ActionID, timestamp: int, occupant: Occupant, action: ActionType, details: str) -> None:
        self.id = actionid
        self.timestamp = timestamp
        self.occupant = occupant
        self.action = action
        self.details = details

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Action.from_id(self.id),
            "order": self.id,
            "timestamp": self.timestamp,
            "occupant": self.occupant.to_dict(),
            "action": self.action,
            "details": self.details,
        }

    @staticmethod
    def from_id(actionid: ActionID) -> str:
        return f"a{actionid}"

    @staticmethod
    def to_id(idstr: str) -> Optional[ActionID]:
        if idstr[0] != 'a':
            return None

        try:
            return ActionID(int(idstr[1:]))
        except ValueError:
            return None
