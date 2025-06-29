from typing import Dict, NewType


UserID = NewType("UserID", int)


class Room:
    def __init__(self, roomid: int, name: str) -> None:
        self.id = roomid
        self.name = name
        # TODO: Hook this into attachments.
        self.icon = "/static/avi.png"

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
        }
