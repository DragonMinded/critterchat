from typing import List, Optional

from ..common import Time
from ..data import Data, Action, Occupant, NewOccupantID, NewActionID, RoomID, UserID


class MessageServiceException(Exception):
    pass


class MessageService:
    def __init__(self, data: Data) -> None:
        self.__data = data

    def get_room_history(self, roomid: RoomID) -> List[Action]:
        history = self.__data.room.get_room_history(roomid)
        history = [e for e in history if e.action in {"message"}]
        return history

    def add_message(self, roomid: RoomID, userid: UserID, message: str) -> Optional[Action]:
        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=userid,
        )

        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action="message",
            details=message,
        )

        self.__data.room.insert_action(roomid, action)
        if action.id is not NewActionID:
            return action
        return None
