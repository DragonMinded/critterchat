from enum import StrEnum
from typing import Dict, NewType, Optional


UserID = NewType("UserID", int)
RoomID = NewType("RoomID", int)
OccupantID = NewType("OccupantID", int)
ActionID = NewType("ActionID", int)


NewUserID = UserID(-1)
NewRoomID = RoomID(-1)
NewOccupantID = OccupantID(-1)
NewActionID = ActionID(-1)


class User:
    def __init__(self, userid: UserID, name: str) -> None:
        self.id = userid
        self.name = name

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": User.from_id(self.id),
            "name": self.name,
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
        self.id = userid
        self.roomid = roomid
        self.info = info

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": User.from_id(self.id),
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


class RoomType(StrEnum):
    UNKNOWN = 'unknown'
    CHAT = 'chat'
    ROOM = 'room'


class Room:
    def __init__(self, roomid: RoomID, name: str, public: bool, last_action: int = 0) -> None:
        self.id = roomid
        self.type = RoomType.UNKNOWN
        self.name = name
        self.public = public
        self.last_action = last_action
        # TODO: Hook this into attachments.
        self.icon = "/static/avi.png"

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Room.from_id(self.id),
            "type": self.type,
            "name": self.name,
            "public": self.public,
            "last_action": self.last_action,
            "icon": self.icon,
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
    def __init__(self, name: str, joined: bool, roomid: Optional[RoomID], userid: Optional[UserID]) -> None:
        self.name = name
        self.joined = joined
        self.roomid = roomid
        self.userid = userid
        # TODO: Hook this into attachments.
        self.icon = "/static/avi.png"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "icon": self.icon,
            "joined": self.joined,
            "roomid": Room.from_id(self.roomid) if self.roomid else None,
            "userid": User.from_id(self.userid) if self.userid else None,
        }


class Occupant:
    def __init__(self, occupantid: OccupantID, userid: UserID, nickname: str = "", inactive: bool = False) -> None:
        self.id = occupantid
        self.userid = userid
        self.nickname = nickname
        self.inactive = inactive
        # TODO: Hook this into attachments.
        self.icon = "/static/avi.png"

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Occupant.from_id(self.id),
            "userid": User.from_id(self.userid),
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
