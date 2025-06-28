import random
import string

from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer
from typing import Optional, Tuple
from typing_extensions import Final
from passlib.hash import pbkdf2_sha512  # type: ignore

from ..common import Time
from .base import BaseData, metadata
from .types import UserID

"""
Table representing a user.
"""
user = Table(
    "user",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True),
    Column("username", String(255), unique=True),
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
    Column("session", String(32), nullable=False, unique=True),
    Column("expiration", Integer),
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
        passhash, salt = self.__compute_password(password=password)
        sql = "UPDATE user SET password = :hash, salt = :salt WHERE id = :userid"
        self.execute(sql, {"hash": passhash, "salt": salt, "userid": userid})

    def from_username(self, username: str) -> Optional[UserID]:
        """
        Given a username, look up a user ID.

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
        return UserID(result["id"])

    def from_session(self, session: str) -> Optional[UserID]:
        """
        Given a previously-opened session, look up an ID.

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
        return UserID(result["id"])

    def create_session(self, userid: UserID, expiration: int = (30 * 86400)) -> str:
        """
        Given an ID, create a session string.

        Parameters:
            userid - ID we wish to start a session for.
            expiration - Number of seconds before this session is invalid.

        Returns:
            A string that can be used as a session ID.
        """
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

    def create_account(self, username: str, password: str) -> Optional[UserID]:
        """
        Create a new user account given a username and password.

        Parameters:
            username - The username that this user will use to login with.
            password - The password that this user will user to login with.
        """

        existing_id = self.from_username(username)
        if existing_id:
            return None

        sql = "INSERT INTO user (`username`, `password`, `salt`) VALUES (:username, :hash, :salt)"
        passhash, salt = self.__compute_password(password=password)
        cursor = self.execute(sql, {"hash": passhash, "salt": salt, "username": username})
        if cursor.rowcount != 1:
            return None
        return UserID(cursor.lastrowid)
