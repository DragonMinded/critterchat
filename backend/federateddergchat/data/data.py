import json
import os
from typing import Any, Dict, Optional, cast

import alembic.config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.engine import Engine, CursorResult  # type: ignore
from sqlalchemy.sql import text
from sqlalchemy.exc import ProgrammingError

from ..config import Config


metadata = MetaData()


class DBCreateException(Exception):
    pass


class _BytesEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, bytes):
            # We're abusing lists here, we have a mixed type
            return ["__bytes__"] + [b for b in obj]
        return json.JSONEncoder.default(self, obj)


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

    def close(self) -> None:
        """
        Close any open data connection.
        """
        # Make sure we don't leak connections between web requests
        if self.__session is not None:
            self.__session.close()
            self.__session = None

    def serialize(self, data: Dict[str, object]) -> str:
        """
        Given an arbitrary dict, serialize it to JSON.
        """
        return json.dumps(data, cls=_BytesEncoder)

    def deserialize(self, data: Optional[str]) -> Dict[str, object]:
        """
        Given a string, deserialize it from JSON.
        """
        if data is None:
            return {}

        def fix(jd: object) -> object:
            if type(jd) == dict:  # noqa
                # Fix each element in the dictionary.
                for key in jd:
                    jd[key] = fix(jd[key])
                return jd

            if type(jd) == list:  # noqa
                # Could be serialized by us, could be a normal list.
                if len(jd) >= 1 and jd[0] == "__bytes__":
                    # This is a serialized bytestring
                    return bytes(jd[1:])

                # Possibly one of these is a dictionary/list/serialized.
                for i in range(len(jd)):
                    jd[i] = fix(jd[i])
                return jd

            # Normal value, its deserialized version is itself.
            return jd

        return cast(Dict[str, object], fix(json.loads(data)))

    def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        safe_write_operation: bool = False,
    ) -> CursorResult:
        """
        Given a SQL string and some parameters, execute the query and return the result.

        Parameters:
            sql - The SQL statement to execute.
            params - Dictionary of parameters which will be substituted into the sql string.

        Returns:
            A SQLAlchemy CursorResult object.
        """
        if self.__session is None:
            raise Exception("Logic error, our database connection was not created!")

        result = self.__session.execute(
            text(sql),
            params if params is not None else {},
        )
        self.__session.commit()
        return result
