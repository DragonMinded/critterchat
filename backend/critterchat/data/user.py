import random
import string

from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import Boolean, String, Integer
from sqlalchemy.dialects.mysql import MEDIUMTEXT as MediumText
from typing import Any, Final
from passlib.hash import pbkdf2_sha512  # type: ignore

from ..common import Time
from .base import BaseData, metadata
from .types import (
    ActionType,
    RoomPurpose,
    User,
    UserPreferences,
    UserSettings,
    UserNotification,
    UserPermission,
    NewActionID,
    NewRoomID,
    NewUserID,
    NewAttachmentID,
    ActionID,
    RoomID,
    UserID,
)

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
    Column("timestamp", Integer, index=True),
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
    Column("about", MediumText),
    Column("icon", Integer),
    Column("timestamp", Integer, index=True),
    mysql_charset="utf8mb4",
)

"""
Table representing a user's instance-wide preferences.
"""
preferences = Table(
    "preferences",
    metadata,
    Column("user_id", Integer, nullable=False, unique=True, index=True),
    Column("rooms_on_top", Boolean),
    Column("combined_messages", Boolean),
    Column("color_scheme", String(8)),
    Column("desktop_size", String(10)),
    Column("mobile_size", String(10)),
    Column("admin_controls", String(10)),
    Column("title_notifs", Boolean),
    Column("mobile_audio_notifs", Boolean),
    Column("audio_notifs", Integer),
    Column("timestamp", Integer, index=True),
    mysql_charset="utf8mb4",
)

"""
Table representing a user's per-session settings.
"""
settings = Table(
    "settings",
    metadata,
    Column("session", String(32), nullable=False, unique=True, index=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("last_room", Integer),
    Column("info", String(8)),
    Column("timestamp", Integer, index=True),
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
    RECOVERY_LENGTH: Final[int] = 12
    INVITE_LENGTH: Final[int] = 6
    PASSWORD_SALT_LENGTH: Final[int] = 32

    SESSION_TYPE_LOGIN: Final[str] = "login"
    SESSION_TYPE_RECOVERY: Final[str] = "recovery"
    SESSION_TYPE_INVITE: Final[str] = "invite"

    def __verify_password(self, *, passhash: str, salt: str, password: str) -> bool:
        actual_password = f"{self.config.password_key}.{salt}.{password}"

        try:
            return bool(pbkdf2_sha512.verify(actual_password, passhash))
        except (ValueError, TypeError):
            return False

    def __compute_password(self, *, password: str) -> tuple[str, str]:
        salt = ''.join(
            random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
            for _ in range(self.PASSWORD_SALT_LENGTH)
        )
        actual_password = f"{self.config.password_key}.{salt}.{password}"
        passhash = pbkdf2_sha512.hash(actual_password)

        return passhash, salt

    def _get_purpose(self, purpose: str) -> RoomPurpose:
        if purpose == RoomPurpose.ROOM:
            return RoomPurpose.ROOM
        elif purpose == RoomPurpose.CHAT:
            return RoomPurpose.CHAT
        elif purpose == RoomPurpose.DIRECT_MESSAGE:
            return RoomPurpose.DIRECT_MESSAGE
        else:
            raise Exception("Logic error, can't find purpose!")

    def validate_password(self, userid: UserID, password: str) -> bool:
        """
        Given a password, validate that the password matches the stored hash

        Parameters:
            userid - Integer user ID, as looked up by one of the above functions.
            password - String, plaintext password that will be hashed

        Returns:
            True if password is valid, False otherwise.
        """
        if userid == NewUserID:
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
        if userid == NewUserID:
            raise Exception("Logic error, should not try to update password for a new user ID!")

        passhash, salt = self.__compute_password(password=password)
        now = Time.now()

        sql = "UPDATE user SET password = :hash, salt = :salt, timestamp = :ts WHERE id = :userid"
        self.execute(sql, {"hash": passhash, "salt": salt, "userid": userid, "ts": now})

        # Also nuke any active recovery strings for the user.
        sql = "DELETE FROM session WHERE id = :userid AND type = :optype"
        self.execute(sql, {"userid": userid, "optype": self.SESSION_TYPE_RECOVERY})

    def validate_invite(self, invite: str) -> bool:
        """
        Given an invite string, look up whether it is valid or not.

        Parameters:
            invite - A string representing a invite key.

        Returns:
            True if the invite is valid, False otherwise.
        """
        # Look up the user account.
        now = Time.now()
        sql = "SELECT id FROM session WHERE session = :invite AND type = :type AND expiration > :timestamp"
        cursor = self.execute(sql, {"invite": invite, "type": self.SESSION_TYPE_INVITE, "timestamp": now})
        if cursor.rowcount != 1:
            # Couldn't find an invite with this type.
            return False

        return True

    def from_username(self, username: str) -> User | None:
        """
        Given a username, look up a user.

        Parameters:
            username - A string representing the user's username.

        Returns:
            User as a class if found, or None if not.
        """
        sql = "SELECT id FROM user WHERE username = :username"
        cursor = self.execute(sql, {"username": username})
        if cursor.rowcount != 1:
            # Couldn't find this username
            return None

        result = cursor.mappings().fetchone()
        return self.get_user(UserID(result["id"]))

    def from_session(self, session: str) -> User | None:
        """
        Given a previously-opened session, look up a user.

        Parameters:
            session - String identifying a session that was opened by create_session.

        Returns:
            User as a class if found, or None if the session is expired or doesn't exist.
        """
        # Look up the user account, making sure to expire old sessions
        now = Time.now()
        sql = "SELECT id FROM session WHERE session = :session AND type = :type AND expiration > :timestamp"
        cursor = self.execute(sql, {"session": session, "type": self.SESSION_TYPE_LOGIN, "timestamp": now})
        if cursor.rowcount != 1:
            # Possibly expired, so let's delete any expired ones.
            self.__cleanup_sessions()

            # Couldn't find a user with this session
            return None

        result = cursor.mappings().fetchone()
        return self.get_user(UserID(result["id"]))

    def from_recovery(self, recovery: str) -> User | None:
        """
        Given a recovery string, look up a user.

        Parameters:
            recovery - A string representing a user recovery key.

        Returns:
            User as a class if found, or None if not.
        """
        # Look up the user account, making sure to expire old sessions
        now = Time.now()
        sql = "SELECT id FROM session WHERE session = :recovery AND type = :type AND expiration > :timestamp"
        cursor = self.execute(sql, {"recovery": recovery, "type": self.SESSION_TYPE_RECOVERY, "timestamp": now})
        if cursor.rowcount != 1:
            # Couldn't find a user with this recovery.
            return None

        result = cursor.mappings().fetchone()
        return self.get_user(UserID(result["id"]))

    def from_invite(self, invite: str) -> User | None:
        """
        Given an invite string, look up the user that generated it. If the invite
        was generated by the system, this will return None since no user created
        the invite.

        Parameters:
            invite - A string representing a invite key.

        Returns:
            User as a class if found, or None if not.
        """
        # Look up the user account.
        now = Time.now()
        sql = "SELECT id FROM session WHERE session = :invite AND type = :type AND expiration > :timestamp"
        cursor = self.execute(sql, {"invite": invite, "type": self.SESSION_TYPE_INVITE, "timestamp": now})
        if cursor.rowcount != 1:
            # Couldn't find a user with this recovery.
            return None

        result = cursor.mappings().fetchone()
        return self.get_user(UserID(result["id"]))

    def create_recovery(self, userid: UserID, expiration: int = (1 * 86400)) -> str:
        """
        Given an ID, create a recovery string.

        Parameters:
            userid - ID we wish to create a recovery string for.
            expiration - Number of seconds before the recovery string is invalid.

        Returns:
            A string that can be used as a password recovery ID.
        """
        if userid == NewUserID:
            raise Exception("Logic error, should not try to create recovery strings for a new user ID!")

        # Create a new recovery string that is unique
        while True:
            recovery = "".join(
                random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
                for _ in range(self.RECOVERY_LENGTH)
            )
            sql = "SELECT session FROM session WHERE session = :recovery"
            cursor = self.execute(sql, {"recovery": recovery})
            if cursor.rowcount == 0:
                # Make sure recovery strings expire in a reasonable amount of time
                expiration = Time.now() + expiration

                # Use that recovery
                sql = """
                    INSERT INTO session (id, session, type, expiration)
                    VALUES (:id, :session, :optype, :expiration)
                """
                cursor = self.execute(
                    sql,
                    {
                        "id": userid,
                        "session": recovery,
                        "optype": self.SESSION_TYPE_RECOVERY,
                        "expiration": expiration,
                    },
                )
                if cursor.rowcount == 1:
                    return recovery

    def create_invite(self, userid: UserID, expiration: int = (1 * 86400)) -> str:
        """
        Given an optional ID, create an invite string.

        Parameters:
            userid - ID we wish to associate the invite with, or NewUserID if the system is doing it.
            expiration - Number of seconds before the invite is invalid.

        Returns:
            A string that can be used as an invite to create an account.
        """

        # Create a new invite that is unique
        while True:
            invite = "".join(
                random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
                for _ in range(self.INVITE_LENGTH)
            )
            sql = "SELECT session FROM session WHERE session = :invite"
            cursor = self.execute(sql, {"invite": invite})
            if cursor.rowcount == 0:
                # Make sure invite strings expire in a reasonable amount of time
                expiration = Time.now() + expiration

                # Use that invite
                sql = """
                    INSERT INTO session (id, session, type, expiration)
                    VALUES (:id, :session, :optype, :expiration)
                """
                cursor = self.execute(
                    sql,
                    {
                        "id": userid,
                        "session": invite,
                        "optype": self.SESSION_TYPE_INVITE,
                        "expiration": expiration,
                    },
                )
                if cursor.rowcount == 1:
                    return invite

    def create_session(self, userid: UserID, expiration: int = (30 * 86400)) -> str:
        """
        Given an ID, create a session string.

        Parameters:
            userid - ID we wish to start a session for.
            expiration - Number of seconds before this session is invalid.

        Returns:
            A string that can be used as a session ID.
        """
        if userid == NewUserID:
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

    def __cleanup_sessions(self) -> None:
        """
        Destroy any defunct sessions.
        """
        sql = "DELETE FROM session WHERE expiration <= :timestamp"
        self.execute(sql, {"timestamp": Time.now()})

        sql = "DELETE FROM settings WHERE session NOT IN (SELECT session FROM session WHERE type = :sesstype)"
        self.execute(sql, {"sesstype": self.SESSION_TYPE_LOGIN})

    def destroy_session(self, session: str) -> None:
        """
        Destroy a previously-created session.

        Parameters:
            session - A session string as returned from create_session.
        """
        # Remove the session token
        sql = "DELETE FROM session WHERE session = :session AND type = :sesstype"
        self.execute(sql, {"session": session, "sesstype": self.SESSION_TYPE_LOGIN})

        sql = "DELETE FROM settings WHERE session = :session"
        self.execute(sql, {"session": session})

        # Also weed out any other defunct sessions
        self.__cleanup_sessions()

    def destroy_invite(self, invite: str) -> None:
        """
        Destroy a previously-created invite.

        Parameters:
            invite - An invite string as returned from create_invite.
        """
        # Remove the invite token
        sql = "DELETE FROM session WHERE session = :session AND type = :sesstype"
        self.execute(sql, {"session": invite, "sesstype": self.SESSION_TYPE_INVITE})

        # Also weed out any other defunct sessions
        self.__cleanup_sessions()

    def create_account(self, username: str, password: str) -> User | None:
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

    def get_settings(self, session: str) -> UserSettings | None:
        """
        Look up a user's settings if they exist.

        Parameters:
            session - The session that this user is logged in under.
        """
        sql = "SELECT * FROM settings WHERE session = :session"
        cursor = self.execute(sql, {"session": session})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return UserSettings(
            userid=UserID(result['user_id']),
            roomid=RoomID(result['last_room']) if result['last_room'] is not None else None,
            info=result['info'],
        )

    def get_any_settings(self, userid: UserID) -> UserSettings | None:
        """
        Look up any of a user's settings if they exist.

        Parameters:
            userid - The user ID we want any settings for, regardless of sesssion.
        """
        sql = "SELECT * FROM settings WHERE user_id = :userid ORDER BY timestamp DESC, session DESC LIMIT 1"
        cursor = self.execute(sql, {"userid": userid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return UserSettings(
            userid=UserID(result['user_id']),
            roomid=RoomID(result['last_room']) if result['last_room'] is not None else None,
            info=result['info'],
        )

    def put_settings(self, session: str, settings: UserSettings) -> None:
        """
        Write a new settings blob to the specified user.

        Parameters:
            session - The user session that we should update settings for.
            settings - The new settings bundle we should persist.
        """
        if settings.userid == NewUserID:
            raise Exception("Logic error, should not try to update settings for a new user ID!")

        sql = """
            INSERT INTO `settings`
                (`session`, `user_id`, `last_room`, `info`, `timestamp`)
            VALUES (:session, :userid, :roomid, :info, :ts)
            ON DUPLICATE KEY UPDATE
            `last_room` = :roomid, `info` = :info, `timestamp` = :ts
        """
        self.execute(sql, {"session": session, "roomid": settings.roomid, "info": settings.info, "userid": settings.userid, 'ts': Time.now()})

    def get_preferences(self, userid: UserID) -> UserPreferences | None:
        """
        Look up a user's preferences if they exist.

        Parameters:
            userid: The user ID that we're looking up preferences for.
        """
        if userid == NewUserID:
            return None

        sql = "SELECT * FROM preferences WHERE user_id = :userid"
        cursor = self.execute(sql, {"userid": userid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        notifications = set()
        bitmask = int(result['audio_notifs'] or 0)
        for notif in UserNotification:
            if (bitmask & notif) == notif:
                notifications.add(notif)

        return UserPreferences(
            userid=UserID(result['user_id']),
            rooms_on_top=bool(result['rooms_on_top']),
            combined_messages=bool(result['combined_messages']),
            color_scheme=str(result['color_scheme'] or "system"),
            desktop_size=str(result['desktop_size'] or "normal"),
            mobile_size=str(result['mobile_size'] or "normal"),
            admin_controls=str(result['admin_controls'] or "visible"),
            title_notifs=bool(result['title_notifs']),
            mobile_audio_notifs=bool(result['mobile_audio_notifs']),
            audio_notifs=notifications,
        )

    def has_updated_preferences(self, userid: UserID, last_checked: int) -> bool:
        """
        Given a user ID and a last checked timestamp, return whether there's an updated user object
        for that user ID or not.
        """

        sql = """
            SELECT user_id FROM preferences WHERE user_id = :userid AND timestamp >= :ts
        """
        cursor = self.execute(sql, {"userid": userid, "ts": last_checked})
        return bool(cursor.rowcount == 1)

    def put_preferences(self, preferences: UserPreferences) -> None:
        """
        Write a new preferences blob to the specified user.

        Parameters:
            preferences - The new preferences bundle we should persist.
        """
        if preferences.userid == NewUserID:
            raise Exception("Logic error, should not try to update preferences for a new user ID!")

        audio_notifs: int = 0
        for an in preferences.audio_notifs:
            audio_notifs |= an

        sql = """
            INSERT INTO `preferences`
                (`user_id`, `rooms_on_top`, `combined_messages`, `color_scheme`, `desktop_size`, `mobile_size`, `admin_controls`, `title_notifs`, `mobile_audio_notifs`, `audio_notifs`, `timestamp`)
            VALUES
                (:userid, :rooms_on_top, :combined_messages, :color_scheme, :desktop_size, :mobile_size, :admin_controls, :title_notifs, :mobile_audio_notifs, :audio_notifs, :ts)
            ON DUPLICATE KEY UPDATE
                `rooms_on_top` = :rooms_on_top,
                `combined_messages` = :combined_messages,
                `color_scheme` = :color_scheme,
                `desktop_size` = :desktop_size,
                `mobile_size` = :mobile_size,
                `admin_controls` = :admin_controls,
                `title_notifs` = :title_notifs,
                `mobile_audio_notifs` = :mobile_audio_notifs,
                `audio_notifs` = :audio_notifs,
                `timestamp` = :ts
        """
        self.execute(sql, {
            "userid": preferences.userid,
            "rooms_on_top": preferences.rooms_on_top,
            "combined_messages": preferences.combined_messages,
            "color_scheme": preferences.color_scheme,
            "desktop_size": preferences.desktop_size,
            "mobile_size": preferences.mobile_size,
            "admin_controls": preferences.admin_controls,
            "title_notifs": preferences.title_notifs,
            "mobile_audio_notifs": preferences.mobile_audio_notifs,
            "audio_notifs": audio_notifs,
            "ts": Time.now()
        })

    def __to_user(self, result: Any) -> User:
        """
        Given a result set, spawn a user for that result.
        """
        nickname = (result['pname'] or None)
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
            result['about'] or '',
            result['icon'],
        )

    def get_user(self, userid: UserID) -> User | None:
        """
        Given a user ID, look up that user.
        """
        if userid == NewUserID:
            return None

        sql = """
            SELECT user.id AS id, user.username AS uname, user.permissions AS permissions, profile.nickname AS pname, profile.about AS about, profile.icon AS icon
            FROM user
            LEFT JOIN profile ON profile.user_id = user.id
            WHERE user.id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return self.__to_user(result)

    def has_updated_user(self, userid: UserID, last_checked: int) -> bool:
        """
        Given a user ID and a last checked timestamp, return whether there's an updated user object
        for that user ID or not.
        """

        sql = """
            SELECT user_id FROM profile WHERE user_id = :userid AND timestamp >= :ts
        """
        cursor = self.execute(sql, {"userid": userid, "ts": last_checked})
        if cursor.rowcount == 1:
            return True

        sql = """
            SELECT id FROM user WHERE id = :userid AND timestamp >= :ts
        """
        cursor = self.execute(sql, {"userid": userid, "ts": last_checked})
        if cursor.rowcount == 1:
            return True

        return False

    def get_last_user_update(self) -> int | None:
        last_update: int | None = None

        cursor = self.execute("SELECT timestamp FROM profile ORDER BY timestamp DESC LIMIT 1")
        if cursor.rowcount == 1:
            result = cursor.mappings().fetchone()
            last_update = int(result['timestamp']) if result['timestamp'] else None

        cursor = self.execute("SELECT timestamp FROM user ORDER BY timestamp DESC LIMIT 1")
        if cursor.rowcount == 1:
            result = cursor.mappings().fetchone()
            newer_update = int(result['timestamp']) if result['timestamp'] else None

            if last_update is None:
                last_update = newer_update
            elif last_update is not None and newer_update is not None:
                last_update = max(last_update, newer_update)

        cursor = self.execute("SELECT timestamp FROM preferences ORDER BY timestamp DESC LIMIT 1")
        if cursor.rowcount == 1:
            result = cursor.mappings().fetchone()
            newer_update = int(result['timestamp']) if result['timestamp'] else None

            if last_update is None:
                last_update = newer_update
            elif last_update is not None and newer_update is not None:
                last_update = max(last_update, newer_update)

        return last_update

    def update_user(self, user: User) -> None:
        """
        Given a valid user, update that user's information.
        """
        if user.id == NewUserID:
            return

        if (
            user.iconid is not None and
            user.iconid != NewAttachmentID
        ):
            iconid = user.iconid
        else:
            iconid = None

        if (user.username == user.nickname) or (not user.nickname):
            nickname = None
        else:
            nickname = user.nickname

        now = Time.now()
        sql = """
            INSERT INTO `profile`
                (`user_id`, `nickname`, `about`, `icon`, `timestamp`)
            VALUES
                (:userid, :name, :about, :iconid, :ts)
            ON DUPLICATE KEY UPDATE
            `nickname` = :name, `about` = :about, `icon` = :iconid, `timestamp` = :ts
        """
        self.execute(sql, {"userid": user.id, "name": nickname, "about": user.about, "iconid": iconid, "ts": now})

        permissions: int = 0
        for perm in user.permissions:
            permissions |= perm

        sql = """
            UPDATE `user` SET `permissions` = :perms, timestamp = :ts WHERE `id` = :userid
        """
        self.execute(sql, {"userid": user.id, "perms": permissions, "ts": now})

    def get_users(self, name: str | None = None) -> list[User]:
        """
        Return a list of all users on the network.
        """

        sql = """
            SELECT user.id AS id, user.username AS uname, user.permissions AS permissions, profile.nickname AS pname, profile.about AS about, profile.icon AS icon
            FROM user
            LEFT JOIN profile ON profile.user_id = user.id
        """

        if name is not None:
            sql += " OR (user.username COLLATE utf8mb4_general_ci LIKE :name OR profile.nickname COLLATE utf8mb4_general_ci LIKE :name)"

        cursor = self.execute(sql, {"name": f"%{name}%"})
        users = [self.__to_user(u) for u in cursor.mappings()]

        # Post-filter by name if requested, so we don't find ourselves all the time.
        if name:
            users = [u for u in users if (name in u.username) or (name in u.nickname)]

        return users

    def get_visible_users(self, userid: UserID, name: str | None = None) -> list[User]:
        """
        Given a user searching, return a list of visible users (users that haven't blocked the
        user, etc). If the name is specified, returns all users with that name.
        """
        if userid == NewUserID:
            return []

        sql = """
            SELECT user.id AS id, user.username AS uname, user.permissions AS permissions, profile.nickname AS pname, profile.about AS about, profile.icon AS icon
            FROM user
            LEFT JOIN profile ON profile.user_id = user.id
            WHERE user.id = :myid
        """

        if name is not None:
            sql += " OR (user.username COLLATE utf8mb4_general_ci LIKE :name OR profile.nickname COLLATE utf8mb4_general_ci LIKE :name)"
        cursor = self.execute(sql, {"myid": userid, "name": f"%{name}%"})
        users = [self.__to_user(u) for u in cursor.mappings()]

        # Post-filter by users who are activated, so we don't display deactivated users.
        users = [u for u in users if UserPermission.ACTIVATED in u.permissions]

        # Post-filter by name if requested, so we don't find ourselves all the time.
        if name:
            users = [u for u in users if (name in u.username) or (name in u.nickname)]

        return users

    def mark_last_seen(self, userid: UserID, roomid: RoomID, actionid: ActionID) -> None:
        """
        Given a user, a room they're in and an action they've seen, mark this action as
        having been seen by this user for this room.
        """

        if userid == NewUserID or roomid == NewRoomID or actionid == NewActionID:
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

    def get_last_seen_counts(self, userid: UserID) -> list[tuple[RoomID, int]]:
        """
        Given a user, grab all of the last seen room/action counts.
        """

        if userid == NewUserID:
            return []

        sql = """
            SELECT lastseen.room_id AS room_id, lastseen.action_id AS action_id, room.purpose AS purpose
            FROM lastseen
            JOIN room ON room.id = lastseen.room_id
            WHERE user_id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        counts = [
            (RoomID(result['room_id']), ActionID(result['action_id']), self._get_purpose(result['purpose']))
            for result in cursor.mappings()
        ]

        def hydrate_existing_count(roomid: RoomID, actionid: ActionID, purpose: RoomPurpose) -> int:
            if purpose == RoomPurpose.DIRECT_MESSAGE:
                types = list(ActionType.unread_dm_types())
            else:
                types = list(ActionType.unread_types())

            sql = """
                SELECT COUNT(id) AS count FROM action WHERE `room_id` = :roomid AND `id` > :actionid AND `action` IN :types
            """
            cursor = self.execute(sql, {"roomid": roomid, "actionid": actionid, "types": types})
            if cursor.rowcount != 1:
                return 0
            result = cursor.mappings().fetchone()
            return int(result["count"])

        # There's probably a SQL way to do this, but I don't want to bang my head against
        # it right now, so it can come in a future improvement.
        computed_counts = [(c[0], hydrate_existing_count(c[0], c[1], c[2])) for c in counts]

        # Now, make sure if we were joined to a room or a chat while we were completely gone
        # that we still count the actions for that room or chat as well.
        seen = [c[0] for c in computed_counts]
        if seen:
            sql = """
                SELECT id, purpose FROM room WHERE id NOT IN :seen AND id IN (
                    SELECT room_id FROM occupant WHERE user_id = :userid AND inactive != TRUE
                )
            """
        else:
            sql = """
                SELECT id, purpose FROM room WHERE id IN (
                    SELECT room_id FROM occupant WHERE user_id = :userid AND inactive != TRUE
                )
            """
        cursor = self.execute(sql, {"seen": seen, "userid": userid})
        extra_rooms = [(RoomID(result['id']), self._get_purpose(result['purpose'])) for result in cursor.mappings()]

        def hydrate_new_count(roomid: RoomID, purpose: RoomPurpose) -> int:
            if purpose == RoomPurpose.DIRECT_MESSAGE:
                types = list(ActionType.unread_dm_types())
            else:
                types = list(ActionType.unread_types())

            sql = """
                SELECT COUNT(id) AS count FROM action WHERE `room_id` = :roomid AND `action` IN :types
            """
            cursor = self.execute(sql, {"roomid": roomid, "types": types})
            if cursor.rowcount != 1:
                return 0
            result = cursor.mappings().fetchone()
            return int(result["count"])

        computed_counts += [(c[0], hydrate_new_count(c[0], c[1])) for c in extra_rooms]
        return computed_counts

    def get_last_seen_actions(self, userid: UserID) -> list[tuple[RoomID, ActionID]]:
        """
        Given a user, grab all of the last seen room/action IDs.
        """

        if userid == NewUserID:
            return []

        sql = """
            SELECT room_id, action_id FROM lastseen WHERE user_id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        return [(RoomID(result['room_id']), ActionID(result['action_id'])) for result in cursor.mappings()]
