from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer
from typing import Set

from .base import BaseData, metadata
from .types import Migration

"""
Table representing a particular data migration.
"""
migration = Table(
    "migration",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("name", String(32), nullable=False),
    mysql_charset="utf8mb4",
)


class MigrationData(BaseData):
    def flag_migrated(self, migration: Migration) -> None:
        """
        Given a migration that was performed, mark it as such so we can look up that it was
        performed in the future and skip doing it again.
        """

        sql = """
            INSERT INTO migration (`name`)
            VALUES (:name)
        """
        self.execute(sql, {"name": migration})

    def get_migrations(self) -> Set[Migration]:
        """
        Look up all known migrations that were performed in the system.
        """

        sql = """
            SELECT `name`
            FROM migration
        """
        cursor = self.execute(sql, {})
        return {Migration(str(result['name'])) for result in cursor.mappings()}
