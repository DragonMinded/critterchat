from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer, Text
from typing import List

from .base import BaseData, metadata
from .types import Room, UserID

"""
Table representing a chat room.
"""
room = Table(
    "room",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True),
    Column("name", String(255), unique=True),
    mysql_charset="utf8mb4",
)

"""
Table representing a chat room's occupants.
"""
occupant = Table(
    "occupant",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True),
    Column("room_id", Integer, nullable=False),
    Column("user_id", Integer, nullable=False),
    mysql_charset="utf8mb4",
)


"""
Table representing a chat room's actions taken by occupants.
"""
action = Table(
    "action",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True),
    Column("timestamp", Integer, nullable=False),
    Column("occupant_id", Integer, nullable=False),
    Column("action", String(32)),
    Column("details", Text),
)


class RoomData(BaseData):
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
                roomid=result['id'],
                name=result['name'],
            )
            for result in cursor.mappings()
        ]
