import json
import random
from contextlib import contextmanager
from typing import Any, Iterator, Protocol, cast

from sqlfragments import Statement, Fragment, statement, fragment

from sqlalchemy.engine.base import Transaction
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import TextClause

from ..config import Config


__all__ = [
    "BaseData",
    "Statement",
    "Fragment",
    "statement",
    "fragment",
]


class ConnectionLike(Protocol):
    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def begin(self) -> Transaction:
        ...

    def begin_nested(self) -> Transaction:
        ...

    def execute(self, text: TextClause, params: dict[str, object] = {}) -> CursorResult[Any]:
        ...

    def close(self) -> None:
        ...


class _BytesEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, bytes):
            # We're abusing lists here, we have a mixed type
            return ["__bytes__"] + [b for b in obj]
        return json.JSONEncoder.default(self, obj)


class BaseData:
    def __init__(self, config: Config, connection: ConnectionLike) -> None:
        """
        Initializes any DB singleton.

        Should only ever be called by Data.

        Parameters:
            config - Global application configuration structure.
            connection - An established DB connection which will be used for all queries.
        """
        self.__config = config
        self.__connection = connection
        self.__depth: list[int] = []

    @property
    def config(self) -> Config:
        return self.__config

    def serialize(self, data: dict[str, object]) -> str:
        """
        Given an arbitrary dict, serialize it to JSON.
        """
        return json.dumps(data, cls=_BytesEncoder)

    def deserialize(self, data: str | None) -> dict[str, object]:
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

        return cast(dict[str, object], fix(json.loads(data)))

    @property
    def upsert_fragment(self) -> Fragment:
        if self.__config.database.backend == "mysql":
            return fragment("ON DUPLICATE KEY UPDATE")
        if self.__config.database.backend == "sqlite":
            return fragment("ON CONFLICT DO UPDATE SET")

        raise NotImplementedError(f"Unsupported database backend {self.__config.database.backend}")

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self.__connection.begin_nested() as txn:
            nonce = random.randint(0, 2 ** 31)
            self.__depth.append(nonce)

            try:
                yield
                txn.commit()

            except Exception:
                txn.rollback()
                raise

            finally:
                newnonce = self.__depth.pop()
                if nonce != newnonce:
                    raise Exception("Logic error, nonce order issue!")

        # Only commit if we didn't throw an exception, otherwise let SQLAlchemy rollback.
        if not self.__depth:
            self.__connection.commit()

    def execute(self, sql: Statement | str, params: dict[str, object] | None = None) -> CursorResult[Any]:
        """
        Given a SQL statement, execute the query and return the result.

        Parameters:
            sql - The SQL statement to execute.

        Returns:
            A SQLAlchemy CursorResult object.
        """
        if isinstance(sql, Statement):
            if params:
                raise ValueError("Logic error, cannot provide Statement and params!")

            actual, params = sql.to_sqlalchemy()
            result = self.__connection.execute(
                text(actual),
                params or {},
            )
        else:
            result = self.__connection.execute(
                text(sql),
                params or {},
            )

        if not self.__depth:
            self.__connection.commit()

        return result
