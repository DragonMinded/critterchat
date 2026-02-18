import copy
import os
from sqlalchemy.engine import Engine
from typing import Any, Dict, Final, List


def _bool(val: Any, default: bool) -> bool:
    if val is None:
        return default
    return bool(val)


class Database:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def address(self) -> str:
        return str(self.__config.get("database", {}).get("address") or "localhost")

    @property
    def database(self) -> str:
        return str(self.__config.get("database", {}).get("database") or "critterchat")

    @property
    def user(self) -> str:
        return str(self.__config.get("database", {}).get("user") or "critterchat")

    @property
    def password(self) -> str:
        return str(self.__config.get("database", {}).get("password") or "critterchat")

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
        return str(self.__config.get("attachments", {}).get("prefix") or "/attachments/")

    @property
    def system(self) -> str:
        return str(self.__config.get("attachments", {}).get("system") or "local")

    @property
    def directory(self) -> str | None:
        directory = self.__config.get("attachments", {}).get("directory")
        return str(directory) if directory else None

    @property
    def attachment_key(self) -> str:
        return str(self.__config.get("attachments", {}).get("attachment_key") or "youalsoreallyshouldhavechangedthistoo")


class Limits:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def about_length(self) -> int:
        return int(self.__config.get("limits", {}).get("about_length") or 64000)

    @property
    def message_length(self) -> int:
        return int(self.__config.get("limits", {}).get("message_length") or 64000)

    @property
    def alt_text_length(self) -> int:
        return int(self.__config.get("limits", {}).get("alt_text_length") or 64000)

    @property
    def icon_size(self) -> int:
        return int(self.__config.get("limits", {}).get("icon_size") or 128)

    @property
    def notification_size(self) -> int:
        return int(self.__config.get("limits", {}).get("notification_size") or 128)

    @property
    def attachment_size(self) -> int:
        return int(self.__config.get("limits", {}).get("attachment_size") or 2048)

    @property
    def attachment_max(self) -> int:
        # Specifically allow 0 as an attachment_max so operators can disable attachments.
        attachment_max = self.__config.get("limits", {}).get("attachment_max")
        if attachment_max is None:
            attachment_max = 4
        return int(attachment_max)


class AccountRegistration:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def enabled(self) -> bool:
        return _bool(self.__config.get("account_registration", {}).get("enabled"), True)

    @property
    def invites(self) -> bool:
        return _bool(self.__config.get("account_registration", {}).get("invites"), False)

    @property
    def auto_approve(self) -> bool:
        return _bool(self.__config.get("account_registration", {}).get("auto_approve"), False)


class MastodonConfig:
    def __init__(self, base_url: str, copy_profile: bool) -> None:
        self.base_url: Final[str] = base_url
        self.copy_profile: Final[bool] = copy_profile


class Authentication:
    def __init__(self, parent_config: "Config") -> None:
        self.__config = parent_config

    @property
    def local(self) -> bool:
        return _bool(self.__config.get("authentication", {}).get("local"), True)

    @property
    def mastodon(self) -> List[MastodonConfig]:
        instances = self.__config.get("authentication", {}).get("mastodon", [])
        if not isinstance(instances, list):
            return []

        retval: List[MastodonConfig] = []
        for instance in instances:
            if not isinstance(instance, dict):
                continue

            base_url = instance.get("base_url")
            copy_profile = instance.get("copy_profile")
            if not base_url:
                continue

            retval.append(MastodonConfig(base_url=base_url, copy_profile=True if copy_profile is None else bool(copy_profile)))

        return retval


class Config(dict[str, Any]):
    def __init__(self, existing_contents: Dict[str, Any] = {}, filename: str | None = None) -> None:
        super().__init__(existing_contents or {})

        self.__path: str | None = None
        if filename:
            self.__path = os.path.dirname(filename)

        self.database = Database(self)
        self.attachments = Attachments(self)
        self.limits = Limits(self)
        self.account_registration = AccountRegistration(self)
        self.authentication = Authentication(self)

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

        clone.__path = self.__path
        return clone

    def set_filename(self, filename: str) -> None:
        self.__path = os.path.dirname(filename)

    @property
    def cookie_key(self) -> str:
        return str(self.get("cookie_key") or "thedergsaysyoureallyneedtochangethis")

    @property
    def password_key(self) -> str:
        return str(self.get("password_key") or "thisisanotherthingyoureallyshouldchange")

    @property
    def name(self) -> str:
        return str(self.get("name") or "Critter Chat Instance")

    @property
    def administrator(self) -> str:
        return str(self.get("administrator") or "nobody")

    @property
    def source(self) -> str | None:
        src = self.get("source")
        return str(src) if src else None

    @property
    def info(self) -> str:
        info_file = self.get("info")
        info = None

        if info_file:
            try:
                if self.__path:
                    info_file = os.path.normpath(os.path.join(self.__path, info_file))

                with open(info_file, "r", encoding="utf-8") as fp:
                    info = fp.read()
            except FileNotFoundError:
                pass

        if not info:
            return "The instance owner has not set any server info."
        else:
            return info

    @property
    def base_url(self) -> str:
        return str(self.get("base_url") or "http://localhost:5678/")

    @property
    def account_base(self) -> str:
        account_base = self.base_url
        if account_base.startswith("http://"):
            account_base = account_base[7:]
        if account_base.startswith("https://"):
            account_base = account_base[8:]
        if "/" in account_base:
            account_base, _ = account_base.split("/", 1)

        return account_base

    @property
    def upload_url(self) -> str:
        value = str(self.get("upload_url") or "")
        if not value:
            value = self.base_url
        return value
