import random
import string

from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import String, Integer, Text
from typing import Any, List, Optional, Tuple
from typing_extensions import Final
from passlib.hash import pbkdf2_sha512  # type: ignore

from ..common import Time
from .base import BaseData, metadata
from .types import ActionType, User, UserSettings, UserPermission, NewActionID, NewRoomID, NewUserID, NewAttachmentID, ActionID, RoomID, UserID

"""
Table representing a user.
"""
user = Table(
    "user",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("username", String(255), unique=True, index=True),
    Column("password", String(1024)),
    Column("salt", String(64)),
    Column("permissions", Integer),
    mysql_charset="utf8mb4",
)

"""
Table representing a user's login session.
"""
session = Table(
    "session",
    metadata,
    Column("id", Integer, nullable=False),
    Column("type", String(32), nullable=False),
    Column("session", String(32), nullable=False, unique=True, index=True),
    Column("expiration", Integer),
    mysql_charset="utf8mb4",
)

"""
Table representing a user's profile.
"""
profile = Table(
    "profile",
    metadata,
    Column("user_id", Integer, nullable=False, unique=True, index=True),
    Column("nickname", String(255)),
    Column("about", Text),
    Column("icon", Integer),
    mysql_charset="utf8mb4",
)

"""
Table representing a user's settings.
"""
settings = Table(
    "settings",
    metadata,
    Column("user_id", Integer, nullable=False, unique=True, index=True),
    Column("last_room", Integer),
    Column("info", String(8)),
    mysql_charset="utf8mb4",
)

"""
Table representing a user's last seen message/action for a given room they're in.
"""
lastseen = Table(
    "lastseen",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("room_id", Integer, nullable=False),
    Column("action_id", Integer, nullable=False),
    UniqueConstraint("user_id", "room_id", name='uidrid'),
    mysql_charset="utf8mb4",
)


class UserData(BaseData):
    SESSION_LENGTH: Final[int] = 32
    PASSWORD_SALT_LENGTH: Final[int] = 32

    SESSION_TYPE_LOGIN: Final[str] = "login"

    def __verify_password(self, *, passhash: str, salt: str, password: str) -> bool:
        actual_password = f"{self.config.password_key}.{salt}.{password}"

        try:
            return bool(pbkdf2_sha512.verify(actual_password, passhash))
        except (ValueError, TypeError):
            return False

    def __compute_password(self, *, password: str) -> Tuple[str, str]:
        salt = ''.join(
            random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
            for _ in range(self.PASSWORD_SALT_LENGTH)
        )
        actual_password = f"{self.config.password_key}.{salt}.{password}"
        passhash = pbkdf2_sha512.hash(actual_password)

        return passhash, salt

    def validate_password(self, userid: UserID, password: str) -> bool:
        """
        Given a password, validate that the password matches the stored hash

        Parameters:
            userid - Integer user ID, as looked up by one of the above functions.
            password - String, plaintext password that will be hashed

        Returns:
            True if password is valid, False otherwise.
        """
        if userid is NewUserID:
            return False

        sql = "SELECT password, salt FROM user WHERE id = :userid"
        cursor = self.execute(sql, {"userid": userid})
        if cursor.rowcount != 1:
            # User doesn't exist, but we have a reference?
            return False

        result = cursor.mappings().fetchone()
        return self.__verify_password(passhash=result["password"], salt=result["salt"], password=password)

    def update_password(self, userid: UserID, password: str) -> None:
        """
        Given a userid and a new password, update the password for that user.

        Parameters:
            userid - Integer user ID, as looked up by one of the above functions.
            password - String, plaintext password that will be hashed
        """
        if userid is NewUserID:
            raise Exception("Logic error, should not try to update password for a new user ID!")

        passhash, salt = self.__compute_password(password=password)
        sql = "UPDATE user SET password = :hash, salt = :salt WHERE id = :userid"
        self.execute(sql, {"hash": passhash, "salt": salt, "userid": userid})

    def from_username(self, username: str) -> Optional[User]:
        """
        Given a username, look up a user.

        Parameters:
            username - A string representing the user's username.

        Returns:
            User ID as an integer if found, or None if not.
        """
        sql = "SELECT id FROM user WHERE username = :username"
        cursor = self.execute(sql, {"username": username})
        if cursor.rowcount != 1:
            # Couldn't find this username
            return None

        result = cursor.mappings().fetchone()
        return self.get_user(UserID(result["id"]))

    def from_session(self, session: str) -> Optional[User]:
        """
        Given a previously-opened session, look up a user.

        Parameters:
            session - String identifying a session that was opened by create_session.

        Returns:
            ID as an integer if found, or None if the session is expired or doesn't exist.
        """
        # Look up the user account, making sure to expire old sessions
        sql = "SELECT id FROM session WHERE session = :session AND type = :type AND expiration > :timestamp"
        cursor = self.execute(sql, {"session": session, "type": self.SESSION_TYPE_LOGIN, "timestamp": Time.now()})
        if cursor.rowcount != 1:
            # Possibly expired, so let's delete any expired ones.
            sql = "DELETE FROM session WHERE expiration < :timestamp"
            self.execute(sql, {"timestamp": Time.now()})

            # Couldn't find a user with this session
            return None

        result = cursor.mappings().fetchone()
        return self.get_user(UserID(result["id"]))

    def create_session(self, userid: UserID, expiration: int = (30 * 86400)) -> str:
        """
        Given an ID, create a session string.

        Parameters:
            userid - ID we wish to start a session for.
            expiration - Number of seconds before this session is invalid.

        Returns:
            A string that can be used as a session ID.
        """
        if userid is NewUserID:
            raise Exception("Logic error, should not try to create session for a new user ID!")

        # Create a new session that is unique
        while True:
            session = "".join(
                random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
                for _ in range(self.SESSION_LENGTH)
            )
            sql = "SELECT session FROM session WHERE session = :session"
            cursor = self.execute(sql, {"session": session})
            if cursor.rowcount == 0:
                # Make sure sessions expire in a reasonable amount of time
                expiration = Time.now() + expiration

                # Use that session
                sql = """
                    INSERT INTO session (id, session, type, expiration)
                    VALUES (:id, :session, :optype, :expiration)
                """
                cursor = self.execute(
                    sql,
                    {
                        "id": userid,
                        "session": session,
                        "optype": self.SESSION_TYPE_LOGIN,
                        "expiration": expiration,
                    },
                )
                if cursor.rowcount == 1:
                    return session

    def destroy_session(self, session: str) -> None:
        """
        Destroy a previously-created session.

        Parameters:
            session - A session string as returned from create_session.
        """
        # Remove the session token
        sql = "DELETE FROM session WHERE session = :session AND type = :sesstype"
        self.execute(sql, {"session": session, "sesstype": self.SESSION_TYPE_LOGIN})

        # Also weed out any other defunct sessions
        sql = "DELETE FROM session WHERE expiration < :timestamp"
        self.execute(sql, {"timestamp": Time.now()})

    def create_account(self, username: str, password: str) -> Optional[User]:
        """
        Create a new user account given a username and password.

        Parameters:
            username - The username that this user will use to login with.
            password - The password that this user will user to login with.
        """

        existing_user = self.from_username(username)
        if existing_user:
            return None

        sql = "INSERT INTO user (`username`, `password`, `salt`) VALUES (:username, :hash, :salt)"
        passhash, salt = self.__compute_password(password=password)
        cursor = self.execute(sql, {"hash": passhash, "salt": salt, "username": username})
        if cursor.rowcount != 1:
            return None
        return self.get_user(UserID(cursor.lastrowid))

    def get_settings(self, userid: UserID) -> Optional[UserSettings]:
        """
        Look up a user's settings if they exist.

        Parameters:
            userid - The ID of the user we want to grab settings for.
        """
        if userid is NewUserID:
            raise Exception("Logic error, should not try to fetch settings for a new user ID!")

        sql = "SELECT * FROM settings WHERE user_id = :userid"
        cursor = self.execute(sql, {"userid": userid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return UserSettings(
            userid=userid,
            roomid=RoomID(result['last_room']) if result['last_room'] is not None else None,
            info=result['info'],
        )

    def put_settings(self, userid: UserID, settings: UserSettings) -> None:
        """
        Write a new settings blob to the specified user.

        Parameters:
            userid - The user ID that we should update settings for.
            settings - The new settings bundle we should persist.
        """
        if userid is NewUserID:
            raise Exception("Logic error, should not try to update settings for a new user ID!")

        sql = """
            INSERT INTO `settings`
                (`user_id`, `last_room`, `info`)
            VALUES (:userid, :roomid, :info)
            ON DUPLICATE KEY UPDATE
            `last_room` = :roomid, `info` = :info
        """
        self.execute(sql, {"roomid": settings.roomid, "info": settings.info, "userid": userid})

    def __to_user(self, result: Any) -> User:
        """
        Given a result set, spawn a user for that result.
        """
        nickname = result['pname']
        if not nickname:
            nickname = result['uname']

        permissions = set()
        bitmask = int(result['permissions'] or 0)
        for perm in UserPermission:
            if (bitmask & perm) == perm:
                permissions.add(perm)

        return User(
            UserID(result['id']),
            result['uname'],
            permissions,
            nickname,
            result['icon'],
        )

    def get_user(self, userid: UserID) -> Optional[User]:
        """
        Given a user ID, look up that user.
        """
        if userid is NewUserID:
            return None

        sql = """
            SELECT user.id AS id, user.username AS uname, user.permissions AS permissions, profile.nickname AS pname, profile.icon AS icon
            FROM user
            LEFT JOIN profile ON profile.user_id = user.id
            WHERE user.id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return self.__to_user(result)

    def update_user(self, user: User) -> None:
        """
        Given a valid user, update that user's information.
        """
        if user.id is NewUserID:
            return

        if (
            user.iconid is not None and
            user.iconid is not NewAttachmentID
        ):
            iconid = user.iconid
        else:
            iconid = None

        if (user.username == user.nickname) or (not user.nickname):
            nickname = None
        else:
            nickname = user.nickname

        sql = """
            INSERT INTO `profile`
                (`user_id`, `nickname`, `icon`)
            VALUES
                (:userid, :name, :iconid)
            ON DUPLICATE KEY UPDATE
            nickname = :name, icon = :iconid
        """
        self.execute(sql, {"userid": user.id, "name": nickname, "iconid": iconid})

        permissions: int = 0
        for perm in user.permissions:
            permissions |= perm

        sql = """
            UPDATE `user` SET `permissions` = :perms WHERE `id` = :userid
        """
        self.execute(sql, {"userid": user.id, "perms": permissions})

    def get_visible_users(self, userid: UserID, name: Optional[str] = None) -> List[User]:
        """
        Given a user searching, return a list of visible users (users that haven't blocked the
        user, etc). If the name is specified, returns all users with that name.
        """
        if userid is NewUserID:
            return []

        sql = """
            SELECT user.id AS id, user.username AS uname, user.permissions AS permissions, profile.nickname AS pname, profile.icon AS icon
            FROM user
            LEFT JOIN profile ON profile.user_id = user.id
            WHERE user.id = :myid
        """

        if name is not None:
            sql += " OR (user.username COLLATE utf8mb4_general_ci LIKE :name OR profile.nickname COLLATE utf8mb4_general_ci LIKE :name)"
        cursor = self.execute(sql, {"myid": userid, "name": f"%{name}%"})
        users = [self.__to_user(u) for u in cursor.mappings()]

        # Post-filter by name if requested, so we don't find ourselves all the time.
        if name:
            users = [u for u in users if (name in u.username) or (name in u.nickname)]

        return users

    def mark_last_seen(self, userid: UserID, roomid: RoomID, actionid: ActionID) -> None:
        """
        Given a user, a room they're in and an action they've seen, mark this action as
        having been seen by this user for this room.
        """

        if userid is NewUserID or roomid is NewRoomID or actionid is NewActionID:
            return

        with self.transaction():
            sql = """
                SELECT action_id FROM lastseen WHERE user_id = :userid AND room_id = :roomid LIMIT 1
            """
            cursor = self.execute(sql, {"userid": userid, "roomid": roomid})
            if cursor.rowcount != 1:
                last = ActionID(0)
            else:
                result = cursor.mappings().fetchone()
                last = ActionID(result['action_id'])

            if actionid <= last:
                # Nothing to do, this is older than our newest message.
                return

            sql = """
                INSERT INTO lastseen (`user_id`, `room_id`, `action_id`)
                VALUES (:userid, :roomid, :actionid)
                ON DUPLICATE KEY UPDATE
                `action_id` = :actionid
            """
            self.execute(sql, {"userid": userid, "roomid": roomid, "actionid": actionid})

    def get_last_seen_counts(self, userid: UserID) -> List[Tuple[RoomID, int]]:
        """
        Given a user, grab all of the last seen room/action counts.
        """

        if userid is NewUserID:
            return []

        sql = """
            SELECT room_id, action_id FROM lastseen WHERE user_id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        counts = [
            (RoomID(result['room_id']), ActionID(result['action_id']))
            for result in cursor.mappings()
        ]

        def hydrate_count(roomid: RoomID, actionid: ActionID) -> int:
            sql = """
                SELECT COUNT(id) AS count FROM action WHERE `room_id` = :roomid AND `id` > :actionid AND `action` IN :types
            """
            cursor = self.execute(sql, {"roomid": roomid, "actionid": actionid, "types": list(ActionType.unread_types())})
            if cursor.rowcount != 1:
                return 0
            result = cursor.mappings().fetchone()
            return int(result["count"])

        # There's probably a SQL way to do this, but I don't want to bang my head against
        # it right now, so it can come in a future improvement.
        return [(c[0], hydrate_count(c[0], c[1])) for c in counts]
