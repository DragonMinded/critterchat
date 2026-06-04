import os
from contextlib import contextmanager
from typing import Final, Iterator, cast

import alembic.config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql import text
from sqlalchemy.exc import ProgrammingError
from sqlfragments import statement

from ..config import Config
from .base import ConnectionLike
from .user import UserData, tables as user_tables
from .room import RoomData, tables as room_tables
from .attachment import AttachmentData, tables as attachment_tables
from .migration import MigrationData, tables as migration_tables
from .mastodon import MastodonData, tables as mastodon_tables
from .types import ActionID, RoomID, UserID, Action, Occupant, User


__all__ = [
    "DBCreateException",
    "Data",
]


class DBCreateException(Exception):
    pass


class RequestCache:
    def __init__(self) -> None:
        self.actions: Final[dict[ActionID, Action | None]] = {}
        self.occupants: Final[dict[RoomID, list[Occupant] | None]] = {}
        self.users: Final[dict[UserID, User | None]] = {}


__metadata: MetaData | None = None


def metadata(dialect: str) -> MetaData:
    global __metadata

    if __metadata:
        return __metadata

    metadata = MetaData()
    for tables in [user_tables, room_tables, attachment_tables, migration_tables, mastodon_tables]:
        tables(dialect, metadata)

    __metadata = metadata
    return metadata


class Data:
    """
    An object that is meant to be used as a singleton, in order to hold DB configuration
    info and provide a set of functions for querying and storing data.
    """

    def __init__(self, config: Config, connection: ConnectionLike | Connection) -> None:
        """
        Initializes the data object.

        Parameters:
            config - A config structure used for various limits.
            connection - A valid SQLAlchemy core connection to the DB.
        """
        self.__config = config
        self.__connection: ConnectionLike = cast(ConnectionLike, connection)
        self.__url = Data.sqlalchemy_url(config)
        self.__metadata: MetaData | None = None
        self._valid = True

        self.user = UserData(config, self.__connection)
        self.room = RoomData(config, self.__connection)
        self.attachment = AttachmentData(config, self.__connection)
        self.migration = MigrationData(config, self.__connection)
        self.mastodon = MastodonData(config, self.__connection)
        self.requestcache = RequestCache()

    def clone(self) -> "Data":
        data = Data(self.__config, self.__connection)
        data._valid = self._valid
        return data

    @contextmanager
    @staticmethod
    def spawn(config: Config) -> Iterator["Data"]:
        with config.database.engine.connect() as connection:
            data = Data(config, connection)

            try:
                yield data
            finally:
                data.close()

    @classmethod
    def sqlalchemy_url(cls, config: Config) -> str:
        if config.database.backend == "mysql":
            return f"mysql://{config.database.user}:{config.database.password}@{config.database.address}/{config.database.database}?charset=utf8mb4"
        if config.database.backend == "sqlite":
            return f"sqlite:///{config.database.file}"
        raise NotImplementedError(f"Unsupported data backend {config.database.backend}")

    @classmethod
    def create_engine(cls, config: Config) -> Engine:
        return create_engine(
            Data.sqlalchemy_url(config),
            pool_recycle=3600,
        )

    def __exists(self) -> bool:
        # See if the DB was already created
        try:
            if self.__config.database.backend == "mysql":
                query = statement(
                    "SELECT count(*) AS count FROM information_schema.TABLES WHERE (TABLE_SCHEMA = %value:schema) AND (TABLE_NAME = 'alembic_version')",
                    schema=self.__config.database.database,
                )
            elif self.__config.database.backend == "sqlite":
                query = statement(
                    "SELECT count(name) AS count FROM sqlite_master WHERE type='table' AND name='alembic_version'",
                )
            else:
                raise NotImplementedError(f"Unsupported data backend {self.__config.database.backend}")

            stmt, args = query.to_sqlalchemy()
            cursor = self.__connection.execute(text(stmt), args)
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
            '-x',
            f'database_dialect={self.__config.database.backend}',
            command,
        ]
        alembicArgs.extend(args)
        os.chdir(base_dir)
        alembic.config.main(argv=alembicArgs)

    def create(self, exist_okay: bool = False) -> None:
        """
        Create any tables that need to be created.
        """
        if self.__exists():
            # Cowardly refused to do anything, we should be using the upgrade path instead.
            if exist_okay:
                # Silently return, with no error. Useful in container init scripts that always
                # want to init the DB if needed, then run the upgrade command.
                return
            else:
                raise DBCreateException('Tables already created, use upgrade to upgrade schema!')

        metadata(self.__config.database.backend).create_all(
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
        diff = compare_metadata(context, metadata(self.__config.database.backend))
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

    def commit(self) -> None:
        """
        Commit any pending transactions to the DB.
        """
        if self._valid:
            self.__connection.commit()

    def close(self) -> None:
        """
        Close any open data connection.
        """
        # Make sure we don't leak connections between web requests
        if self._valid:
            self.__connection.close()
            self._valid = False
