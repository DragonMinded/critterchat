from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer, Text
from typing import List, Optional
from typing_extensions import Final

from .base import BaseData, metadata
from .types import Action, Occupant, Room, ActionID, OccupantID, RoomID, UserID

"""
Table representing a chat room.
"""
room = Table(
    "room",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("name", String(255), unique=True),
    mysql_charset="utf8mb4",
)

"""
Table representing a chat room's occupants.
"""
occupant = Table(
    "occupant",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("room_id", Integer, nullable=False, index=True),
    Column("nickname", String(255)),
    mysql_charset="utf8mb4",
)


"""
Table representing a chat room's actions taken by occupants.
"""
action = Table(
    "action",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("timestamp", Integer, nullable=False),
    Column("room_id", Integer, nullable=False, index=True),
    Column("occupant_id", Integer, nullable=False),
    Column("action", String(32)),
    Column("details", Text),
)


class RoomData(BaseData):
    MAX_HISTORY: Final[int] = 100

    def get_joined_rooms(self, userid: UserID) -> List[Room]:
        """
        Given a user ID, look up the rooms that user is in.

        Parameters:
            userid - The ID of the user that we want rooms for.

        Returns:
            list of Room objects representing the rooms the user is in.
        """
        sql = "SELECT id, name FROM room WHERE id in (SELECT room_id FROM occupant WHERE user_id = :userid)"
        cursor = self.execute(sql, {"userid": userid})
        return [
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
            )
            for result in cursor.mappings()
        ]

    def get_room_history(self, roomid: RoomID, before: Optional[ActionID] = None, after: Optional[ActionID] = None) -> List[Action]:
        """
        Given a room ID, and possibly a pagination offset, fetch recent room history.

        Parameters:
            before - Optional ActionID that we should fetch actions before.
            after - Optional ActionID that we should fetch actions after.

        Returns:
            list of Action objects representing actions taken in the room.
        """

        # First, grab all the actions we can.
        sql = "SELECT id, timestamp, occupant_id, action, details FROM action WHERE room_id = :roomid ORDER BY id DESC LIMIT :limit"
        cursor = self.execute(sql, {"roomid": roomid, "limit": self.MAX_HISTORY})
        data = [x for x in cursor.mappings()]

        # Now, scoop up all of our occupants that we should look up.
        occupantids = {x['occupant_id'] for x in data}
        sql = "SELECT id, user_id, nickname FROM occupant WHERE id IN (:occupantids)"
        cursor = self.execute(sql, {"occupantids": occupantids})
        mapping = {OccupantID(x['id']): (UserID(x['user_id']), x['nickname']) for x in cursor.mappings()}

        def occupant(occupantid: int) -> Occupant:
            oid = OccupantID(occupantid)
            return Occupant(occupantid=oid, userid=mapping[oid][0], nickname=mapping[oid][1])

        # Now, combine them all.
        return [
            Action(
                actionid=ActionID(x['id']),
                timestamp=x['timestamp'],
                occupant=occupant(x['occupant_id']),
                action=x['action'],
                details=x['details'],
            )
            for x in data
        ]
