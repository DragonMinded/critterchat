from typing import Dict, NewType, Optional


UserID = NewType("UserID", int)
RoomID = NewType("RoomID", int)
OccupantID = NewType("OccupantID", int)
ActionID = NewType("ActionID", int)


class Room:
    def __init__(self, roomid: RoomID, name: str) -> None:
        self.id = roomid
        self.name = name
        # TODO: Hook this into attachments.
        self.icon = "/static/avi.png"

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Room.from_id(self.id),
            "name": self.name,
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


class Occupant:
    def __init__(self, occupantid: OccupantID, userid: UserID, nickname: str) -> None:
        self.id = occupantid
        self.userid = userid
        self.nickname = nickname
        # TODO: Hook this into attachments.
        self.icon = "/static/avi.png"

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": Occupant.from_id(self.id),
            "userid": f"u{self.userid}",
            "nickname": self.nickname,
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


class Action:
    def __init__(self, actionid: ActionID, timestamp: int, occupant: Occupant, action: str, details: str) -> None:
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
