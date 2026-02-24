import contextlib
from typing import Any, Iterable, Iterator

from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import String, Integer, Boolean, JSON

from ..common import Time
from .base import BaseData, Fragment, fragment, statement, metadata
from .types import (
    Action,
    ActionType,
    Occupant,
    Room,
    RoomPurpose,
    UserPermission,
    NewUserID,
    NewActionID,
    NewAttachmentID,
    NewOccupantID,
    NewRoomID,
    ActionID,
    AttachmentID,
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
    Column("topic", String(255)),
    Column("autojoin", Boolean, default=False),
    Column("moderated", Boolean, default=False),
    Column("icon", Integer),
    Column("purpose", String(10), nullable=False),
    Column("last_action", Integer, nullable=False),
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
    Column("moderator", Boolean, default=False),
    Column("muted", Boolean, default=False),
    Column("nickname", String(255)),
    Column("icon", Integer),
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
    Column("occupant_id", Integer),
    Column("action", String(32)),
    Column("details", JSON),
    mysql_charset="utf8mb4",
)


class RoomData(BaseData):
    def _get_oldest_action(self, room_ids: list[RoomID]) -> dict[RoomID, ActionID | None]:
        if not room_ids:
            return {}

        cursor = self.execute(statement(
            """
                SELECT room_id, MIN(id) AS action_id
                FROM action
                WHERE room_id IN %value:ids
                GROUP BY room_id
            """,
            ids=room_ids,
        ))
        retval: dict[RoomID, ActionID | None] = {rid: None for rid in room_ids}
        for result in cursor.mappings():
            retval[RoomID(result['room_id'])] = ActionID(result['action_id'])
        return retval

    def _get_newest_action(self, room_ids: list[RoomID]) -> dict[RoomID, ActionID | None]:
        if not room_ids:
            return {}

        cursor = self.execute(statement(
            """
                SELECT room_id, MAX(id) AS action_id
                FROM action
                WHERE room_id IN %value:ids
                GROUP BY room_id
            """,
            ids=room_ids,
        ))
        retval: dict[RoomID, ActionID | None] = {rid: None for rid in room_ids}
        for result in cursor.mappings():
            retval[RoomID(result['room_id'])] = ActionID(result['action_id'])
        return retval

    def _hydrate_actions(self, rooms: list[Room]) -> list[Room]:
        oldest_actions = self._get_oldest_action([r.id for r in rooms])
        newest_actions = self._get_newest_action([r.id for r in rooms])
        for room in rooms:
            room.oldest_action = oldest_actions.get(room.id)
            room.newest_action = newest_actions.get(room.id)
        return rooms

    def _get_purpose(self, purpose: str) -> RoomPurpose:
        if purpose == RoomPurpose.ROOM:
            return RoomPurpose.ROOM
        elif purpose == RoomPurpose.CHAT:
            return RoomPurpose.CHAT
        elif purpose == RoomPurpose.DIRECT_MESSAGE:
            return RoomPurpose.DIRECT_MESSAGE
        else:
            raise Exception("Logic error, can't find purpose!")

    def get_joined_rooms(self, userid: UserID, include_left: bool = False) -> list[Room]:
        """
        Given a user ID, look up the rooms that user is in.

        Parameters:
            userid - The ID of the user that we want rooms for.

        Returns:
            list of Room objects representing the rooms the user is in.
        """
        if userid == NewUserID:
            return []

        filters: list[Fragment] = [fragment("user_id = %value", userid)]
        if include_left:
            filters.append(fragment("inactive != TRUE"))

        cursor = self.execute(statement(
            """
                SELECT id, name, topic, icon, purpose, moderated, last_action
                FROM room
                WHERE id in (SELECT room_id FROM occupant WHERE %andlist)
            """,
            filters,
        ))
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def get_left_rooms(self, userid: UserID) -> list[Room]:
        """
        Given a user ID, look up the rooms that user was is in but has left.

        Parameters:
            userid - The ID of the user that we want rooms for.

        Returns:
            list of Room objects representing the rooms the user was previously in but isn't in now.
        """
        if userid == NewUserID:
            return []

        sql = """
            SELECT id, name, topic, icon, purpose, moderated, last_action FROM room WHERE id in (
                SELECT room_id FROM occupant WHERE user_id = :userid AND inactive = TRUE
            )
        """
        cursor = self.execute(sql, {"userid": userid})
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def get_joined_room_occupants(self, userid: UserID) -> dict[RoomID, Occupant]:
        """
        Given a user ID, look up the occupant data for that user in each room they're in.

        Parameters:
            roomid - The ID of the user that we want occupants for.
        """
        if userid == NewUserID:
            return {}

        sql = """
            SELECT
                occupant.id AS id,
                occupant.user_id AS user_id,
                occupant.room_id AS room_id,
                occupant.nickname AS onick,
                occupant.inactive AS inactive,
                occupant.moderator AS moderator,
                occupant.muted AS muted,
                occupant.icon AS oicon,
                profile.nickname AS pnick,
                profile.icon AS picon,
                user.username AS unick,
                user.permissions AS permissions
            FROM occupant
            LEFT JOIN profile ON occupant.user_id = profile.user_id
            LEFT JOIN user ON occupant.user_id = user.id
            WHERE occupant.user_id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        return {RoomID(o['room_id']): self.__to_occupant(o) for o in cursor.mappings()}

    def get_matching_rooms(self, userid: UserID, name: str | None = None) -> list[Room]:
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
        if userid == NewUserID:
            return []

        sql = """
            SELECT id, name, topic, icon, purpose, moderated, last_action FROM room WHERE id in (
                SELECT room_id FROM occupant WHERE user_id = :userid AND inactive != TRUE
            )
        """
        if name is not None:
            sql += " AND (name IS NULL OR name = '' OR name COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"userid": userid, "name": f"%{name}%"})
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def get_rooms(self, name: str | None = None) -> list[Room]:
        """
        Look up all existing rooms, potentially matching any that match the name.

        Parameters:
            name - The name of the room we want to match.

        Returns:
            list of Room objects representing the rooms on the network
        """
        sql = """
            SELECT id, name, topic, icon, purpose, moderated, last_action FROM room
        """
        if name is not None:
            sql += " WHERE (name IS NULL OR name = '' OR name COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"name": f"%{name}%"})
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def get_public_rooms(self, name: str | None = None) -> list[Room]:
        """
        Look up all public rooms, potentially matching any that match the name.

        Parameters:
            name - The name of the room we want to match.

        Returns:
            list of Room objects representing the public rooms on the network
        """
        sql = """
            SELECT id, name, topic, icon, purpose, moderated, last_action FROM room WHERE purpose = :purpose
        """
        if name is not None:
            sql += " AND (name IS NULL OR name = '' OR name COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"name": f"%{name}%", "purpose": RoomPurpose.ROOM})
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def get_visible_rooms(self, userid: UserID, name: str | None = None) -> list[Room]:
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
        if userid == NewUserID:
            return []

        sql = """
            SELECT id, name, topic, icon, purpose, moderated, last_action FROM room WHERE purpose = :purpose
        """
        if name is not None:
            sql += " AND (name IS NULL OR name = '' OR name COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"userid": userid, "name": f"%{name}%", "purpose": RoomPurpose.ROOM})
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def get_autojoin_rooms(self) -> list[Room]:
        """
        Look up all rooms that are marked for auto-join on this network.

        Returns:
            list of Room objects representing the rooms the user will auto-join.
        """
        sql = """
            SELECT id, name, topic, icon, purpose, moderated, last_action FROM room WHERE autojoin = TRUE
        """

        cursor = self.execute(sql, {})
        return self._hydrate_actions([
            Room(
                roomid=RoomID(result['id']),
                name=result['name'],
                topic=result['topic'],
                purpose=self._get_purpose(str(result['purpose'])),
                moderated=bool(result['moderated']),
                last_action_timestamp=result['last_action'],
                iconid=AttachmentID(result['icon']) if result['icon'] else None,
                deficonid=None,
            )
            for result in cursor.mappings()
        ])

    def set_room_autojoin(self, roomid: RoomID, autojoin: bool) -> None:
        """
        Given a room, set it's autojoin to true or false.

        Params:
            roomid - The ID of the room we're setting.
            autojoin - A boolean for whether the room should be autojoin or not.
        """
        if roomid == NewRoomID:
            return

        sql = """
            UPDATE room SET `autojoin` = :autojoin WHERE `id` = :roomid
        """
        self.execute(sql, {'roomid': roomid, 'autojoin': autojoin})

    def get_room(self, roomid: RoomID) -> Room | None:
        """
        Given a room ID, get that room.

        Parameters:
            roomid - The ID of the room we want to fetch.
        """

        if roomid == NewRoomID:
            return None

        sql = """
            SELECT * FROM room WHERE id = :roomid
        """
        cursor = self.execute(sql, {"roomid": roomid})
        if cursor.rowcount != 1:
            return None
        result = cursor.mappings().fetchone()
        room_id = RoomID(result['id'])
        oldest_actions = self._get_oldest_action([room_id])
        newest_actions = self._get_newest_action([room_id])

        return Room(
            roomid=room_id,
            name=result['name'],
            topic=result['topic'],
            purpose=self._get_purpose(str(result['purpose'])),
            moderated=bool(result['moderated']),
            last_action_timestamp=result['last_action'],
            oldest_action=oldest_actions.get(room_id),
            newest_action=newest_actions.get(room_id),
            iconid=AttachmentID(result['icon']) if result['icon'] else None,
            deficonid=None,
        )

    def get_occupant_room(self, occupantid: OccupantID) -> Room | None:
        """
        Given an occupant ID, get the room that occupant is in.

        Parameters:
            occupantid - The ID of the occupant we want to fetch the room for.
        """

        if occupantid == NewOccupantID:
            return None

        sql = """
            SELECT room_id FROM occupant WHERE id = :occupantid
        """
        cursor = self.execute(sql, {"occupantid": occupantid})
        if cursor.rowcount != 1:
            return None
        result = cursor.mappings().fetchone()
        room_id = RoomID(result['room_id'])
        return self.get_room(room_id)

    def create_room(self, room: Room) -> None:
        """
        Given some parameters for a room, create that room and return it.

        Parameters:
            room - The room object to create.
        """

        if room.id != NewRoomID:
            raise Exception("Logic error, cannot insert already-persisted room as a new room!")

        timestamp = Time.now()
        sql = """
            INSERT INTO room (`name`, `topic`, `moderated`, `purpose`, `last_action`, `icon`) VALUES (:name, :topic, :moderated, :purpose, :timestamp, :icon)
        """
        cursor = self.execute(sql, {"name": room.name, "topic": room.topic, "moderated": room.moderated, "purpose": room.purpose, "timestamp": timestamp, "icon": room.iconid})
        if cursor.rowcount != 1:
            return None
        newroom = self.get_room(RoomID(cursor.lastrowid))
        if newroom:
            room.id = newroom.id
            room.name = newroom.name
            room.topic = newroom.topic
            room.purpose = newroom.purpose
            room.iconid = newroom.iconid
            room.last_action_timestamp = timestamp

    def join_room(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room to join and a user who wants to join, try joining that room.

        Parameters:
            roomid - ID of the room we wish to join.
            userid - ID of the user wishing to join.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return None

        with self.transaction():
            # First, figure out if we're already joined.
            sql = """
                SELECT id FROM occupant WHERE `user_id` = :userid AND `room_id` = :roomid AND `inactive` != TRUE
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            already_joined = cursor.rowcount > 0

            sql = """
                INSERT INTO occupant (`user_id`, `room_id`, `inactive`) VALUES (:userid, :roomid, FALSE)
                ON DUPLICATE KEY UPDATE `inactive` = FALSE
            """
            self.execute(sql, {"userid": userid, "roomid": roomid})

            if not already_joined:
                occupant = Occupant(
                    occupantid=NewOccupantID,
                    userid=userid,
                )
                action = Action(
                    actionid=NewActionID,
                    timestamp=Time.now(),
                    occupant=occupant,
                    action=ActionType.JOIN,
                    details={},
                )
                self.insert_action(roomid, action)

    def shadow_join_room(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room to join and a user who wants to join, try shadow joining that room. That just
        means that if there's already an entry in the occupants table for this entry, ignore it.
        Otherwise, join the user in an inactive state. Note that this never generates an action
        because it's meant for associating DMs with different chatters.

        Parameters:
            roomid - ID of the room we wish to join.
            userid - ID of the user wishing to join.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return None

        with self.transaction():
            # First, figure out if we're already joined.
            sql = """
                SELECT id FROM occupant WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            already_joined = cursor.rowcount > 0

            # Now, if we're not, then shadow-join it.
            if not already_joined:
                sql = """
                    INSERT INTO occupant (`user_id`, `room_id`, `inactive`) VALUES (:userid, :roomid, TRUE)
                """
                self.execute(sql, {"userid": userid, "roomid": roomid})

    def leave_room(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room to leave and a user who wants to leave, try leaving that room.

        Parameters:
            roomid - ID of the room we wish to leave.
            userid - ID of the user wishing to leave.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return

        # insert_action will ignore actions for anyone already out of the room.
        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=userid,
        )
        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.LEAVE,
            details={},
        )
        self.insert_action(roomid, action)

        sql = """
            UPDATE occupant SET inactive = TRUE WHERE `user_id` = :userid AND `room_id` = :roomid
        """
        self.execute(sql, {"userid": userid, "roomid": roomid})

    def grant_room_moderator(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room and a user who should be set as a moderator, set that user as a moderator.

        Parameters:
            roomid - ID of the room we wish to update.
            userid - ID of the user wishing to be moderator.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return

        with self.transaction():
            sql = """
                SELECT moderator FROM occupant WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            if cursor.rowcount != 1:
                # Not in room, can't modify.
                return
            result = cursor.mappings().fetchone()
            moderator = bool(result['moderator'])
            if moderator:
                # Already a moderator.
                return

            sql = """
                UPDATE occupant SET moderator = TRUE WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            self.execute(sql, {"userid": userid, "roomid": roomid})

            occupant = Occupant(
                occupantid=NewOccupantID,
                userid=userid,
            )
            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.CHANGE_USERS,
                details={},
            )
            self.insert_action(roomid, action)

    def revoke_room_moderator(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room and a user who should be unset as a moderator, unset that user as a moderator.

        Parameters:
            roomid - ID of the room we wish to update.
            userid - ID of the user wishing to not be moderator.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return

        with self.transaction():
            sql = """
                SELECT moderator FROM occupant WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            if cursor.rowcount != 1:
                # Not in room, can't modify.
                return
            result = cursor.mappings().fetchone()
            moderator = bool(result['moderator'])
            if not moderator:
                # Already not a moderator.
                return

            sql = """
                UPDATE occupant SET moderator = FALSE WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            self.execute(sql, {"userid": userid, "roomid": roomid})

            occupant = Occupant(
                occupantid=NewOccupantID,
                userid=userid,
            )
            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.CHANGE_USERS,
                details={},
            )
            self.insert_action(roomid, action)

    def mute_room_occupant(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room and a user who should be muted, mute that user.

        Parameters:
            roomid - ID of the room we wish to update.
            userid - ID of the user that should be muted.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return

        with self.transaction():
            sql = """
                SELECT muted FROM occupant WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            if cursor.rowcount != 1:
                # Not in room, cannot modify.
                return
            result = cursor.mappings().fetchone()
            muted = bool(result['muted'])
            if muted:
                # Alredy muted.
                return

            sql = """
                UPDATE occupant SET muted = TRUE WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            self.execute(sql, {"userid": userid, "roomid": roomid})

            occupant = Occupant(
                occupantid=NewOccupantID,
                userid=userid,
            )
            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.CHANGE_USERS,
                details={},
            )
            self.insert_action(roomid, action)

    def unmute_room_occupant(self, roomid: RoomID, userid: UserID) -> None:
        """
        Given a room and a user who should be unmuted, unmute that user.

        Parameters:
            roomid - ID of the room we wish to update.
            userid - ID of the user that should be unmuted.
        """
        if userid == NewUserID or roomid == NewRoomID:
            return

        with self.transaction():
            sql = """
                SELECT muted FROM occupant WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            if cursor.rowcount != 1:
                # Not in room, cannot modify.
                return
            result = cursor.mappings().fetchone()
            muted = bool(result['muted'])
            if not muted:
                # Already unmuted.
                return

            sql = """
                UPDATE occupant SET muted = FALSE WHERE `user_id` = :userid AND `room_id` = :roomid
            """
            self.execute(sql, {"userid": userid, "roomid": roomid})

            occupant = Occupant(
                occupantid=NewOccupantID,
                userid=userid,
            )
            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.CHANGE_USERS,
                details={},
            )
            self.insert_action(roomid, action)

    def update_room(self, room: Room, userid: UserID) -> None:
        """
        Given a valid room, update its details to match the given object.
        """
        if room.id == NewRoomID:
            return

        if (
            room.iconid is not None and
            room.iconid != NewAttachmentID
        ):
            iconid = room.iconid
        else:
            iconid = None

        sql = """
            UPDATE room SET name = :name, topic = :topic, icon = :iconid, moderated = :moderated WHERE id = :roomid
        """
        self.execute(sql, {"roomid": room.id, "name": room.name, "topic": room.topic, "iconid": iconid, "moderated": room.moderated})

        if userid == NewUserID:
            occupant = None
        else:
            occupant = Occupant(
                occupantid=NewOccupantID,
                userid=userid,
            )

        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.CHANGE_INFO,
            details={"name": room.name, "topic": room.topic, "iconid": iconid, "moderated": room.moderated},
        )
        self.insert_action(room.id, action)

    def __to_occupant(self, result: Any) -> Occupant:
        """
        Given a result set, spawn an occupant for that result.
        """
        nickname = (result['onick'] or None)
        if not nickname:
            nickname = (result['pnick'] or None)
        if not nickname:
            nickname = result['unick']

        icon = result['oicon']
        if not icon:
            icon = result['picon']

        permissions = set()
        bitmask = int(result['permissions'] or 0)
        for perm in UserPermission:
            if (bitmask & perm) == perm:
                permissions.add(perm)

        # Treat a user as inactive if they're deactivated or if they've left the channel.
        inactive = bool(result['inactive'])
        if UserPermission.ACTIVATED not in permissions:
            inactive = True

        # Treat a user as a moderator if they're an administrator.
        moderator = bool(result['moderator'])
        if UserPermission.ADMINISTRATOR in permissions:
            moderator = True

        # Mute status is simpler.
        muted = bool(result['muted'])

        return Occupant(
            OccupantID(result['id']),
            UserID(result['user_id']),
            username=result['unick'],
            nickname=nickname,
            inactive=inactive,
            moderator=moderator,
            muted=muted,
            iconid=AttachmentID(icon) if icon else None,
        )

    def get_room_occupants(self, roomid: RoomID, include_left: bool = False) -> list[Occupant]:
        """
        Given a room ID, look up all occupants of that room and their names and avatars.

        Parameters:
            roomid - The ID of the room that we want occupants for.
        """
        if roomid == NewRoomID:
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
                occupant.moderator AS moderator,
                occupant.muted AS muted,
                occupant.icon AS oicon,
                profile.nickname AS pnick,
                profile.icon AS picon,
                user.username AS unick,
                user.permissions AS permissions
            FROM occupant
            LEFT JOIN profile ON occupant.user_id = profile.user_id
            LEFT JOIN user ON occupant.user_id = user.id
            WHERE occupant.room_id = :roomid {extra}
        """
        cursor = self.execute(sql, {"roomid": roomid})
        return [self.__to_occupant(o) for o in cursor.mappings()]

    def get_room_occupant(self, occupantid: OccupantID) -> Occupant | None:
        """
        Given an occupant ID, look up that occupant. Note that this will return occupants
        that have left, which is necessary for linking names/nicknames in chat history.

        Parameters:
            occupantid - The ID of the occupant we're curious about.
        """
        if occupantid == NewOccupantID:
            return None

        sql = """
            SELECT
                occupant.id AS id,
                occupant.user_id AS user_id,
                occupant.nickname AS onick,
                occupant.inactive AS inactive,
                occupant.moderator AS moderator,
                occupant.muted AS muted,
                occupant.icon AS oicon,
                profile.nickname AS pnick,
                profile.icon AS picon,
                user.username AS unick,
                user.permissions AS permissions
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

    def get_last_action(self) -> ActionID | None:
        """
        Gets the last action that was performed for this entire application.
        """

        sql = """
            SELECT id FROM action ORDER BY id DESC LIMIT 1
        """
        cursor = self.execute(sql, {})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return ActionID(result['id'])

    def get_room_history(
        self,
        roomid: RoomID,
        before: ActionID | None = None,
        after: ActionID | None = None,
        types: Iterable[ActionType] | None = None,
        limit: int | None = None,
    ) -> list[Action]:
        """
        Given a room ID, and possibly a pagination offset, fetch recent room history.

        Parameters:
            before - Optional ActionID that we should fetch actions before.
            after - Optional ActionID that we should fetch actions after.

        Returns:
            list of Action objects representing actions taken in the room.
        """
        if roomid == NewRoomID:
            return []

        # First, grab all the actions we can.
        filters: list[Fragment] = [fragment("room_id = %value", roomid)]
        if before is not None:
            filters.append(fragment("id < %value", before))
        if after is not None:
            filters.append(fragment("id > %value", after))
        if types is not None:
            filters.append(fragment("action IN %inlist", [str(t) for t in types]))

        querylimit: Fragment | None = None
        if limit is not None:
            querylimit = fragment("LIMIT %value", limit)

        cursor = self.execute(statement(
            """
                SELECT id, timestamp, occupant_id, action, details
                FROM action
                WHERE %andlist:filters
                ORDER BY id DESC %fragment:limit
            """,
            filters=filters,
            limit=querylimit,
        ))
        data = [x for x in cursor.mappings()]

        if not data:
            return []

        # Now, scoop up all of our occupants that we should look up.
        occupantids = {x['occupant_id'] for x in data if x['occupant_id'] is not None}

        if occupantids:
            sql = """
                SELECT
                    occupant.id AS id,
                    occupant.user_id AS user_id,
                    occupant.nickname AS onick,
                    occupant.inactive AS inactive,
                    occupant.moderator AS moderator,
                    occupant.muted AS muted,
                    occupant.icon AS oicon,
                    profile.nickname AS pnick,
                    profile.icon AS picon,
                    user.username AS unick,
                    user.permissions AS permissions
                FROM occupant
                LEFT JOIN profile ON occupant.user_id = profile.user_id
                LEFT JOIN user ON occupant.user_id = user.id
                WHERE occupant.id IN :occupantids
            """
            cursor = self.execute(sql, {"occupantids": list(occupantids)})
            occupants = [self.__to_occupant(o) for o in cursor.mappings()]
        else:
            occupants = []
        mapping = {oc.id: oc for oc in occupants}

        # Now, combine them all.
        return [
            Action(
                actionid=ActionID(x['id']),
                timestamp=x['timestamp'],
                occupant=mapping[OccupantID(x['occupant_id'])] if x['occupant_id'] is not None else None,
                action=x['action'],
                details=self.deserialize(str(x['details'] or "{}")),
            )
            for x in data
        ]

    @contextlib.contextmanager
    def lock_actions(self) -> Iterator[None]:
        """
        Locks the actions table for exclusive write, when needing to attach data to a new
        attachment without other clients polling incomplete actions. Use in a with block.
        """
        sql = "LOCK TABLES room WRITE, action WRITE, occupant READ, profile READ, user READ"
        self.execute(sql, {})
        try:
            yield
        finally:
            sql = "UNLOCK TABLES"
            self.execute(sql, {})

    def get_action(self, actionid: ActionID) -> Action | None:
        """
        Given an action ID, look up that action and return it.

        Returns:
            Action object representing action looked up or None if the action doesn't exist.
        """
        if actionid == NewActionID:
            return None

        sql = """
            SELECT id, timestamp, occupant_id, action, details
            FROM action
            WHERE id = :actionid
        """
        cursor = self.execute(sql, {"actionid": actionid})
        if cursor.rowcount != 1:
            # This action doesn't exist.
            return None

        result = cursor.mappings().fetchone()

        # Now, scoop up the occupant that goes with this action.
        occupantid = result['occupant_id']
        if occupantid:
            sql = """
                SELECT
                    occupant.id AS id,
                    occupant.user_id AS user_id,
                    occupant.nickname AS onick,
                    occupant.inactive AS inactive,
                    occupant.moderator AS moderator,
                    occupant.muted AS muted,
                    occupant.icon AS oicon,
                    profile.nickname AS pnick,
                    profile.icon AS picon,
                    user.username AS unick,
                    user.permissions AS permissions
                FROM occupant
                LEFT JOIN profile ON occupant.user_id = profile.user_id
                LEFT JOIN user ON occupant.user_id = user.id
                WHERE occupant.id = :occupantid
            """
            cursor = self.execute(sql, {"occupantid": occupantid})
            occupants = [self.__to_occupant(o) for o in cursor.mappings()]
        else:
            occupants = []
        mapping = {oc.id: oc for oc in occupants}

        # Now, combine them all.
        return Action(
            actionid=ActionID(result['id']),
            timestamp=result['timestamp'],
            occupant=mapping[OccupantID(result['occupant_id'])] if result['occupant_id'] is not None else None,
            action=result['action'],
            details=self.deserialize(str(result['details'] or "{}")),
        )

    def insert_action(self, roomid: RoomID, action: Action) -> None:
        """
        Given a room ID and an action, insert that action into the room's history.

        Parameters:
            roomid - ID of the room that the action should go into.
            action - The action itself that should be added.
        """
        if roomid == NewRoomID:
            raise Exception("Logic error, should not try to insert an action to a new room ID!")

        if action.id != NewActionID:
            raise Exception("Logic error, cannot insert already-persisted action as a new action!")

        if action.occupant:
            if action.occupant.userid == NewUserID:
                # Cannot insert an action as a fake user. This should be performed as an action without
                # an occupant.
                return

            # First, find the occupant ID.
            sql = "SELECT id FROM occupant WHERE room_id = :roomid AND user_id = :userid AND inactive != TRUE LIMIT 1"
            cursor = self.execute(sql, {"roomid": roomid, "userid": action.occupant.userid})
            if cursor.rowcount != 1:
                # Trying to insert an action and we're not in the room?
                return

            result = cursor.mappings().fetchone()
            occupant = result['id']

            if action.occupant.id != NewOccupantID:
                if action.occupant.id != OccupantID(occupant):
                    # Trying to send as an occupant that we're not?
                    return

        else:
            if action.action not in {ActionType.CHANGE_INFO}:
                # Cannot insert this action type without an occupant to link to.
                return

            occupant = None

        # Now, figure out the room type for last action calculations.
        sql = "SELECT purpose FROM room WHERE id = :roomid"
        cursor = self.execute(sql, {"roomid": roomid})
        if cursor.rowcount != 1:
            # Trying to insert an action and the room doesn't exist?
            return

        result = cursor.mappings().fetchone()
        purpose = self._get_purpose(result['purpose'])

        # Now, attempt to insert the action itself.
        sql = """
            INSERT INTO action
                (`room_id`, `timestamp`, `occupant_id`, `action`, `details`)
            VALUES
                (:roomid, :ts, :oid, :action, :details)
        """
        cursor = self.execute(sql, {
            "roomid": roomid, "ts": action.timestamp, "oid": occupant, "action": action.action, "details": self.serialize(action.details)
        })
        if cursor.rowcount != 1:
            return

        # Hydrate what we've just persisted.
        action.id = ActionID(cursor.lastrowid)
        if action.occupant and occupant is not None:
            action.occupant.id = OccupantID(occupant)

            # Now, hydrate the occupant itself so the nickname is present on the response.
            newoccupant = self.get_room_occupant(action.occupant.id)
            if newoccupant:
                action.occupant.nickname = newoccupant.nickname
                action.occupant.inactive = newoccupant.inactive
                action.occupant.iconid = newoccupant.iconid

        if purpose == RoomPurpose.DIRECT_MESSAGE:
            types = ActionType.unread_dm_types()
        else:
            types = ActionType.unread_types()

        # Finally, record the action timestamp into the room if it is an action that causes badging.
        if action.action in types:
            sql = """
                UPDATE room SET `last_action` = :ts WHERE `id` = :roomid AND `last_action` < :ts
            """
            self.execute(sql, {"roomid": roomid, "ts": action.timestamp})

    def update_action(self, action: Action) -> None:
        """
        Given an action, update the values that are allowed to change in the DB.
        """
        if action.id == NewActionID:
            return

        # Right now, only the details can be updated. In the future, this should allow updating
        # the attachment list as well once we support editing messages.
        sql = """
            UPDATE action SET details = :details WHERE id = :id LIMIT 1
        """
        self.execute(sql, {"id": action.id, "details": self.serialize(action.details)})
