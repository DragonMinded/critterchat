from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer
from typing import List, Optional

from .base import BaseData, metadata
from .types import MastodonInstance

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


class MastodonData(BaseData):
    def get_instances(self) -> List[MastodonInstance]:
        """
        Return all known instances that we've registered with.
        """

        sql = "SELECT * FROM mastodon_instance"
        cursor = self.execute(sql, {})
        return [
            MastodonInstance(
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
        self.execute(sql, {
            "base_url": instance.base_url,
            "client_id": instance.client_id,
            "client_secret": instance.client_secret,
        })
