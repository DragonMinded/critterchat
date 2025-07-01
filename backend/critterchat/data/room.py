from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer, Boolean, Text
from typing import Any, List, Optional
from typing_extensions import Final

from .base import BaseData, metadata
from .types import Action, Occupant, Room, NewUserID, NewActionID, NewOccupantID, NewRoomID, ActionID, OccupantID, RoomID, UserID

"""
Table representing a chat room.
"""
room = Table(
    "room",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("name", String(255)),
    Column("public", Boolean),
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
        if userid is NewUserID:
            return []

        sql = "SELECT id, name, public FROM room WHERE id in (SELECT room_id FROM occupant WHERE user_id = :userid)"
        cursor = self.execute(sql, {"userid": userid})
        return [
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                public=result['public'],
            )
            for result in cursor.mappings()
        ]

    def __to_occupant(self, result: Any) -> Occupant:
        """
        Given a result set, spawn an occupant for that result.
        """
        nickname = result['onick']
        if not nickname:
            nickname = result['pnick']
        if not nickname:
            nickname = result['unick']

        return Occupant(
            OccupantID(result['id']),
            UserID(result['user_id']),
            nickname,
        )

    def get_room_occupants(self, roomid: RoomID) -> List[Occupant]:
        """
        Given a room ID, look up all occupants of that room and their names and avatars.

        Parameters:
            roomid - The ID of the room that we want occupants for.
        """
        if roomid is NewRoomID:
            return []

        sql = """
            SELECT
                occupant.id AS id,
                occupant.user_id AS user_id,
                occupant.nickname AS onick,
                profile.nickname AS pnick,
                user.username AS unick
            FROM occupant
            LEFT JOIN profile ON occupant.user_id = profile.user_id
            LEFT JOIN user ON occupant.user_id = user.id
            WHERE occupant.room_id = :roomid
        """
        cursor = self.execute(sql, {"roomid": roomid})
        return [self.__to_occupant(o) for o in cursor.mappings()]

    def get_room_occupant(self, occupantid: OccupantID) -> Optional[Occupant]:
        """
        Given an occupant ID, look up that occupant.

        Parameters:
            occupantid - The ID of the occupant we're curious about.
        """
        if occupantid is NewOccupantID:
            return None

        sql = """
            SELECT
                occupant.id AS id,
                occupant.user_id AS user_id,
                occupant.nickname AS onick,
                profile.nickname AS pnick,
                user.username AS unick
            FROM occupant
            LEFT JOIN profile ON occupant.user_id = profile.user_id
            LEFT JOIN user ON occupant.user_id = user.id
            WHERE occupant.id = :occupantid
        """
        cursor = self.execute(sql, {"occupantid": occupantid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return self.__to_occupant(result)

    def get_room_history(
        self,
        roomid: RoomID,
        before: Optional[ActionID] = None,
        after: Optional[ActionID] = None,
        limit: Optional[int] = None,
    ) -> List[Action]:
        """
        Given a room ID, and possibly a pagination offset, fetch recent room history.

        Parameters:
            before - Optional ActionID that we should fetch actions before.
            after - Optional ActionID that we should fetch actions after.

        Returns:
            list of Action objects representing actions taken in the room.
        """
        if roomid is NewRoomID:
            return []

        # First, grab all the actions we can.
        limitclauses = ""
        if before:
            limitclauses += " AND id < :before"
        if after:
            limitclauses += " AND id > :after"

        sql = f"""
            SELECT id, timestamp, occupant_id, action, details
            FROM action
            WHERE room_id = :roomid
            {limitclauses}
            ORDER BY id DESC LIMIT :limit
        """
        cursor = self.execute(sql, {"roomid": roomid, "limit": limit or self.MAX_HISTORY, 'before': before, 'after': after})
        data = [x for x in cursor.mappings()]

        if not data:
            return []

        # Now, scoop up all of our occupants that we should look up.
        occupantids = {x['occupant_id'] for x in data}
        sql = """
            SELECT
                occupant.id AS id,
                occupant.user_id AS user_id,
                occupant.nickname AS onick,
                profile.nickname AS pnick,
                user.username AS unick
            FROM occupant
            LEFT JOIN profile ON occupant.user_id = profile.user_id
            LEFT JOIN user ON occupant.user_id = user.id
            WHERE occupant.id IN :occupantids
        """
        cursor = self.execute(sql, {"occupantids": list(occupantids)})
        occupants = [self.__to_occupant(o) for o in cursor.mappings()]
        mapping = {oc.id: oc for oc in occupants}

        # Now, combine them all.
        return [
            Action(
                actionid=ActionID(x['id']),
                timestamp=x['timestamp'],
                occupant=mapping[OccupantID(x['occupant_id'])],
                action=x['action'],
                details=x['details'],
            )
            for x in data
        ]

    def insert_action(self, roomid: RoomID, action: Action) -> None:
        """
        Given a room ID and an action, insert that action into the room's history.

        Parameters:
            roomid - ID of the room that the action should go into.
            action - The action itself that should be added.
        """
        if roomid is NewRoomID:
            raise Exception("Logic error, should not try to insert an action to a new room ID!")

        if action.id is not NewActionID:
            raise Exception("Logic error, cannot insert already-persisted action as a new action!")

        # First, find the occupant ID.
        sql = "SELECT id FROM occupant WHERE room_id = :roomid AND user_id = :userid LIMIT 1"
        cursor = self.execute(sql, {"roomid": roomid, "userid": action.occupant.userid})
        if cursor.rowcount != 1:
            # Trying to send a message and we're not in the room?
            return

        result = cursor.mappings().fetchone()
        occupant = result['id']

        if action.occupant.id is not NewOccupantID:
            if action.occupant.id != OccupantID(occupant):
                # Trying to send as an occupant that we're not?
                return

        # Now, attempt to insert the action itself.
        sql = """
            INSERT INTO action
                (`room_id`, `timestamp`, `occupant_id`, `action`, `details`)
            VALUES
                (:roomid, :ts, :oid, :action, :details)
        """
        cursor = self.execute(sql, {
            "roomid": roomid, "ts": action.timestamp, "oid": occupant, "action": action.action, "details": action.details
        })
        if cursor.rowcount != 1:
            return

        # Hydrate what we've just persisted.
        action.id = ActionID(cursor.lastrowid)
        action.occupant.id = OccupantID(occupant)

        # Now, hydrate the occupant itself so the nickname is present on the response.
        newoccupant = self.get_room_occupant(action.occupant.id)
        if newoccupant:
            action.occupant.nickname = newoccupant.nickname
