import copy
from sqlalchemy.engine import Engine
from typing import Any, Dict


class Database:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def address(self) -> str:
        return str(self.__config.get("database", {}).get("address", "localhost"))

    @property
    def database(self) -> str:
        return str(self.__config.get("database", {}).get("database", "fdc"))

    @property
    def user(self) -> str:
        return str(self.__config.get("database", {}).get("user", "fdc"))

    @property
    def password(self) -> str:
        return str(self.__config.get("database", {}).get("password", "fdc"))

    @property
    def engine(self) -> Engine:
        engine = self.__config.get("database", {}).get("engine")
        if engine is None:
            raise Exception("Config object is not instantiated properly, no SQLAlchemy engine present!")
        if not isinstance(engine, Engine):
            raise Exception("Config object is not instantiated properly, engine property is not a SQLAlchemy Engine!")
        return engine


class Config(dict[str, Any]):
    def __init__(self, existing_contents: Dict[str, Any] = {}) -> None:
        super().__init__(existing_contents or {})

        self.database = Database(self)

    def clone(self) -> "Config":
        # Somehow its not possible to clone this object if an instantiated Engine is present,
        # so we do a little shenanigans here.
        engine = self.get("database", {}).get("engine")
        if engine is not None:
            self["database"]["engine"] = None

        clone = Config(copy.deepcopy(self))

        if engine is not None:
            self["database"]["engine"] = engine
            clone["database"]["engine"] = engine

        return clone
