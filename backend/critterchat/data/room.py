from typing import Any, List, Optional
from typing_extensions import Final

from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import String, Integer, Boolean, Text

from .base import BaseData, metadata
from .types import (
    Action,
    ActionType,
    Occupant,
    Room,
    NewUserID,
    NewActionID,
    NewOccupantID,
    NewRoomID,
    ActionID,
    OccupantID,
    RoomID,
    UserID,
)

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
    Column("inactive", Boolean, default=False),
    Column("nickname", String(255)),
    UniqueConstraint("user_id", "room_id", name='uidrid'),
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

    def get_joined_rooms(self, userid: UserID, include_left: bool = False) -> List[Room]:
        """
        Given a user ID, look up the rooms that user is in.

        Parameters:
            userid - The ID of the user that we want rooms for.

        Returns:
            list of Room objects representing the rooms the user is in.
        """
        if userid is NewUserID:
            return []

        if include_left:
            extra = ""
        else:
            extra = "AND inactive != TRUE"

        sql = f"""
            SELECT id, name, public FROM room WHERE id in (
                SELECT room_id FROM occupant WHERE user_id = :userid {extra}
            )
        """
        cursor = self.execute(sql, {"userid": userid})
        return [
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                public=result['public'],
            )
            for result in cursor.mappings()
        ]

    def get_matching_rooms(self, userid: UserID, name: Optional[str] = None) -> List[Room]:
        """
        Given a user ID, look up the rooms that user is in that match the search criteria.
        Note that this will also return rooms with unset names if you specify the name,
        because the calling layer will infer the room name.

        Parameters:
            userid - The ID of the user that we want rooms for.
            name - The name of the room we want to match.

        Returns:
            list of Room objects representing the rooms the user is in.
        """
        if userid is NewUserID:
            return []

        sql = """
            SELECT id, name, public FROM room WHERE id in (
                SELECT room_id FROM occupant WHERE user_id = :userid AND inactive != TRUE
            )
        """
        if name is not None:
            sql += " AND (name IS NULL OR name = '' OR name COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"userid": userid, "name": f"%{name}%"})
        return [
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                public=result['public'],
            )
            for result in cursor.mappings()
        ]

    def get_visible_rooms(self, userid: UserID, name: Optional[str] = None) -> List[Room]:
        """
        Given a user ID, look up the rooms that user can see that match the search criteria.
        Note that this will also return rooms with unset names if you specify the name,
        because the calling layer will infer the room name.

        Parameters:
            userid - The ID of the user that we want rooms for.
            name - The name of the room we want to match.

        Returns:
            list of Room objects representing the rooms the user is in.
        """
        if userid is NewUserID:
            return []

        sql = """
            SELECT id, name, public FROM room WHERE public = TRUE
        """
        if name is not None:
            sql += " AND (name IS NULL OR name = '' OR name COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"userid": userid, "name": f"%{name}%"})
        return [
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                public=result['public'],
            )
            for result in cursor.mappings()
        ]

    def get_room(self, roomid: RoomID) -> Optional[Room]:
        """
        Given a room ID, get that room.

        Parameters:
            roomid - The ID of the room we want to fetch.
        """

        if roomid is NewRoomID:
            return None

        sql = """
            SELECT * FROM room WHERE id = :roomid
        """
        cursor = self.execute(sql, {"roomid": roomid})
        if cursor.rowcount != 1:
            return None
        result = cursor.mappings().fetchone()
        return Room(
            roomid=RoomID(result['id']),
            name=result['name'],
            public=result['public'],
        )

    def create_room(self, room: Room) -> None:
        """
        Given some parameters for a room, create that room and return it.

        Parameters:
            room - The room object to create.
        """

        if room.id is not NewRoomID:
            raise Exception("Logic error, cannot insert already-persisted room as a new room!")

        sql = """
            INSERT INTO room (`name`, `public`) VALUES (:name, :public)
        """
        cursor = self.execute(sql, {"name": room.name, "public": room.public})
        if cursor.rowcount != 1:
            return None
        newroom = self.get_room(RoomID(cursor.lastrowid))
        if newroom:
            room.id = newroom.id
            room.name = newroom.name
            room.public = newroom.public

    def join_room(self, roomid: RoomID, userid: UserID) -> Optional[Occupant]:
        """
        Given a room to join and a user who wants to join, try joining that room.

        Parameters:
            roomid - ID of the room we wish to join.
            userid - ID of the user wishing to join.
        """
        if userid is NewUserID or roomid is NewRoomID:
            return None

        sql = """
            INSERT INTO occupant (`user_id`, `room_id`, `inactive`) VALUES (:userid, :roomid, FALSE)
            ON DUPLICATE KEY UPDATE `inactive` = FALSE
        """
        cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
        if cursor.rowcount != 1:
            return None
        return self.get_room_occupant(OccupantID(cursor.lastrowid))

    def leave_room(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room to leave and a user who wants to leave, try leaving that room.

        Parameters:
            roomid - ID of the room we wish to leave.
            userid - ID of the user wishing to leave.
        """
        if userid is NewUserID or roomid is NewRoomID:
            return

        sql = """
            UPDATE occupant SET inactive = TRUE WHERE `user_id` = :userid AND `room_id` = :roomid
        """
        self.execute(sql, {"userid": userid, "roomid": roomid})

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
            inactive=result['inactive'],
        )

    def get_room_occupants(self, roomid: RoomID, include_left: bool = False) -> List[Occupant]:
        """
        Given a room ID, look up all occupants of that room and their names and avatars.

        Parameters:
            roomid - The ID of the room that we want occupants for.
        """
        if roomid is NewRoomID:
            return []

        if include_left:
            extra = ""
        else:
            extra = "AND occupant.inactive != TRUE"

        sql = f"""
            SELECT
                occupant.id AS id,
                occupant.user_id AS user_id,
                occupant.nickname AS onick,
                occupant.inactive AS inactive,
                profile.nickname AS pnick,
                user.username AS unick
            FROM occupant
            LEFT JOIN profile ON occupant.user_id = profile.user_id
            LEFT JOIN user ON occupant.user_id = user.id
            WHERE occupant.room_id = :roomid {extra}
        """
        cursor = self.execute(sql, {"roomid": roomid})
        return [self.__to_occupant(o) for o in cursor.mappings()]

    def get_room_occupant(self, occupantid: OccupantID) -> Optional[Occupant]:
        """
        Given an occupant ID, look up that occupant. Note that this will return occupants
        that have left, which is necessary for linking names/nicknames in chat history.

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
                occupant.inactive AS inactive,
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
                occupant.inactive AS inactive,
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
        sql = "SELECT id FROM occupant WHERE room_id = :roomid AND user_id = :userid AND inactive != TRUE LIMIT 1"
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
            action.occupant.inactive = newoccupant.inactive
