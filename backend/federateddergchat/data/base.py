import json
from typing import Dict, Optional, cast

from sqlalchemy import MetaData
from sqlalchemy.orm import scoped_session
from sqlalchemy.engine import CursorResult  # type: ignore
from sqlalchemy.sql import text

from ..config import Config


metadata = MetaData()


class _BytesEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, bytes):
            # We're abusing lists here, we have a mixed type
            return ["__bytes__"] + [b for b in obj]
        return json.JSONEncoder.default(self, obj)


class BaseData:
    def __init__(self, config: Config, session: scoped_session) -> None:
        """
        Initializes any DB singleton.

        Should only ever be called by Data.

        Parameters:
            config - Global application configuration structure.
            session - An established DB session which will be used for all queries.
        """
        self.__config = config
        self.__session = session

    @property
    def config(self) -> Config:
        return self.__config

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
        params: Optional[Dict[str, object]] = None,
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
