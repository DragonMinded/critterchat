import copy
from sqlalchemy.engine import Engine
from typing import Any, Dict, Optional


class Database:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def address(self) -> str:
        return str(self.__config.get("database", {}).get("address", "localhost"))

    @property
    def database(self) -> str:
        return str(self.__config.get("database", {}).get("database", "critterchat"))

    @property
    def user(self) -> str:
        return str(self.__config.get("database", {}).get("user", "critterchat"))

    @property
    def password(self) -> str:
        return str(self.__config.get("database", {}).get("password", "critterchat"))

    @property
    def engine(self) -> Engine:
        engine = self.__config.get("database", {}).get("engine")
        if engine is None:
            raise Exception("Config object is not instantiated properly, no SQLAlchemy engine present!")
        if not isinstance(engine, Engine):
            raise Exception("Config object is not instantiated properly, engine property is not a SQLAlchemy Engine!")
        return engine


class Attachments:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def prefix(self) -> str:
        return str(self.__config.get("attachments", {}).get("prefix", "/attachments/"))

    @property
    def system(self) -> str:
        return str(self.__config.get("attachments", {}).get("system", "local"))

    @property
    def directory(self) -> Optional[str]:
        directory = self.__config.get("attachments", {}).get("directory")
        return str(directory) if directory else None


class Config(dict[str, Any]):
    def __init__(self, existing_contents: Dict[str, Any] = {}) -> None:
        super().__init__(existing_contents or {})

        self.database = Database(self)
        self.attachments = Attachments(self)

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

    @property
    def cookie_key(self) -> str:
        return str(self.get("cookie_key", "thedergsaysyoureallyneedtochangethis"))

    @property
    def password_key(self) -> str:
        return str(self.get("password_key", "thisisanotherthingyoureallyshouldchange"))

    @property
    def name(self) -> str:
        return str(self.get("name", "Critter Chat Instance"))
