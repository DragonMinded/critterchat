from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import String, Integer
from typing import List, Optional

from .base import BaseData, metadata
from .types import MastodonInstance, MastodonInstanceID, UserID

"""
Table representing a mastodon instance that we auth against.
"""
mastodon_instance = Table(
    "mastodon_instance",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("base_url", String(512), nullable=False, unique=True, index=True),
    Column("client_id", String(256), nullable=False),
    Column("client_secret", String(256), nullable=False),
    mysql_charset="utf8mb4",
)

"""
Table representing a link between a user in our system and a Mastodon account
on a remote instance. This is used for authentication/login.
"""
mastodon_account_link = Table(
    "mastodon_account_link",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("instance_id", Integer, nullable=False, index=True),
    Column("username", String(128), nullable=False),
    UniqueConstraint("instance_id", "username", name='instance_id_username'),
    mysql_charset="utf8mb4",
)


class MastodonData(BaseData):
    def get_instances(self) -> List[MastodonInstance]:
        """
        Return all known instances that we've registered with.
        """

        sql = "SELECT * FROM mastodon_instance"
        cursor = self.execute(sql, {})
        return [
            MastodonInstance(
                instanceid=MastodonInstanceID(result['id']),
                base_url=str(result['base_url']),
                client_id=str(result['client_id']),
                client_secret=str(result['client_secret']),
            ) for result in cursor.mappings()
        ]

    def lookup_instance(self, base_url: str) -> Optional[MastodonInstance]:
        """
        Given a base URL for an instance, look up any existing credentials we've
        obtained during registration.
        """

        sql = "SELECT * FROM mastodon_instance WHERE base_url = :base_url LIMIT 1"
        cursor = self.execute(sql, {"base_url": base_url})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return MastodonInstance(
            instanceid=MastodonInstanceID(result['id']),
            base_url=str(result['base_url']),
            client_id=str(result['client_id']),
            client_secret=str(result['client_secret']),
        )

    def store_instance(self, instance: MastodonInstance) -> None:
        """
        Given an instance, store it to the DB. If the instnace already exists, update
        the client ID and secret.
        """

        sql = """
            INSERT INTO `mastodon_instance`
                (`base_url`, `client_id`, `client_secret`)
            VALUES (:base_url, :client_id, :client_secret)
            ON DUPLICATE KEY UPDATE
                `client_id` = :client_id, `client_secret` = :client_secret
        """
        cursor = self.execute(sql, {
            "base_url": instance.base_url,
            "client_id": instance.client_id,
            "client_secret": instance.client_secret,
        })
        if cursor.rowcount != 1:
            return

        # Hydrate what we've just persisted.
        instance.id = MastodonInstanceID(cursor.lastrowid)

    def lookup_account_link(self, base_url: str, username: str) -> Optional[UserID]:
        """
        Given a base URL of an instance and a username that was found on that
        instance, return the user ID of the local user that we have linked.
        """

        sql = """
            SELECT user_id
            FROM mastodon_account_link
            WHERE instance_id IN (
                SELECT id FROM mastodon_instance WHERE base_url = :base_url
            ) AND username = :username
            LIMIT 1
        """
        cursor = self.execute(sql, {"base_url": base_url, "username": username})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return UserID(result['user_id'])

    def store_account_link(self, base_url: str, username: str, user_id: UserID) -> None:
        """
        Given a base URL, a mastodon username, and a valid local user, create a link
        between the mastodon user and the local account for authentication purposes.
        """

        instance = self.lookup_instance(base_url)
        if not instance:
            return

        sql = """
            INSERT INTO mastodon_account_link (`user_id`, `instance_id`, `username`)
            VALUES (:user_id, :instance_id, :username)
        """
        self.execute(sql, {"user_id": user_id, "instance_id": instance.id, "username": username})
