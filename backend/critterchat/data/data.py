import os
from typing import Optional

import alembic.config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text
from sqlalchemy.exc import ProgrammingError

from ..config import Config
from .base import metadata
from .user import UserData
from .room import RoomData
from .attachment import AttachmentData


__all__ = [
    "DBCreateException",
    "Data",
    "metadata",
]


class DBCreateException(Exception):
    pass


class Data:
    """
    An object that is meant to be used as a singleton, in order to hold DB configuration
    info and provide a set of functions for querying and storing data.
    """

    def __init__(self, config: Config) -> None:
        """
        Initializes the data object.

        Parameters:
            config - A config structure with a 'database' section which is used
                     to initialize an internal DB connection.
        """
        session_factory = sessionmaker(
            bind=config.database.engine,
            autoflush=True,
        )
        self.__config = config
        self.__session: Optional[scoped_session] = scoped_session(session_factory)
        self.__url = Data.sqlalchemy_url(config)

        self.user = UserData(config, self.__session)
        self.room = RoomData(config, self.__session)
        self.attachment = AttachmentData(config, self.__session)

    @classmethod
    def sqlalchemy_url(cls, config: Config) -> str:
        return f"mysql://{config.database.user}:{config.database.password}@{config.database.address}/{config.database.database}?charset=utf8mb4"

    @classmethod
    def create_engine(cls, config: Config) -> Engine:
        return create_engine(
            Data.sqlalchemy_url(config),
            pool_recycle=3600,
        )

    def __exists(self) -> bool:
        # See if the DB was already created
        if self.__session is None:
            raise Exception("Logic error, our database connection was not created!")

        try:
            cursor = self.__session.execute(text("SELECT count(*) AS count FROM information_schema.TABLES WHERE (TABLE_SCHEMA = :schema) AND (TABLE_NAME = 'alembic_version')"), {"schema": self.__config.database.database})
            return bool(cursor.mappings().fetchone()['count'] == 1)
        except ProgrammingError:
            return False

    def __alembic_cmd(self, command: str, *args: str) -> None:
        base_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'migrations')
        alembicArgs = [
            '-c',
            os.path.join(base_dir, 'alembic.ini'),
            '-x',
            f'script_location={base_dir}',
            '-x',
            f'sqlalchemy.url={self.__url}',
            command,
        ]
        alembicArgs.extend(args)
        os.chdir(base_dir)
        alembic.config.main(argv=alembicArgs)

    def create(self) -> None:
        """
        Create any tables that need to be created.
        """
        if self.__exists():
            # Cowardly refused to do anything, we should be using the upgrade path instead.
            raise DBCreateException('Tables already created, use upgrade to upgrade schema!')

        metadata.create_all(
            self.__config.database.engine.connect(),
            checkfirst=True,
        )

        # Stamp the end revision as if alembic had created it, so it can take off after this.
        self.__alembic_cmd(
            'stamp',
            'head',
        )

    def generate(self, message: str, allow_empty: bool) -> None:
        """
        Generate upgrade scripts using alembic.
        """
        if not self.__exists():
            raise DBCreateException('Tables have not been created yet, use create to create them!')

        # Verify that there are actual changes, and refuse to create empty migration scripts
        context = MigrationContext.configure(self.__config.database.engine.connect(), opts={'compare_type': True})
        diff = compare_metadata(context, metadata)
        if (not allow_empty) and (len(diff) == 0):
            raise DBCreateException('There is nothing different between code and the DB, refusing to create migration!')

        self.__alembic_cmd(
            'revision',
            '--autogenerate',
            '-m',
            message,
        )

    def upgrade(self) -> None:
        """
        Upgrade an existing DB to the current model.
        """
        if not self.__exists():
            raise DBCreateException('Tables have not been created yet, use create to create them!')

        self.__alembic_cmd(
            'upgrade',
            'head',
        )

    def downgrade(self, tag: str) -> None:
        """
        Downgrade an existing db to a specific model. Accepts a hash or relative syntax.
        """
        if not self.__exists():
            raise DBCreateException('Tables have not been created yet, use create to create them!')

        self.__alembic_cmd(
            'downgrade',
            tag,
        )

    def close(self) -> None:
        """
        Close any open data connection.
        """
        # Make sure we don't leak connections between web requests
        if self.__session is not None:
            self.__session.close()
            self.__session = None
