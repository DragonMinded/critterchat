from typing import Any
from unittest.mock import MagicMock

from critterchat.config import Config
from critterchat.data import Data


def MockData() -> Data:
    data = MagicMock()
    data.user = MagicMock()
    data.room = MagicMock()
    data.attachment = MagicMock()
    data.migration = MagicMock()
    data.mastodon = MagicMock()

    return data


def MockConfig() -> Config:
    config = Config({
        "cookie_key": "cookie_key",
        "password_key": "password_key",
        "name": "Critter Chat Unit Tests",
        "base_url": "http://localhost/",
        "attachments": {
            "prefix": "/attachments/",
            "system": "local",
            "attachment_key": "attachment_key",
        },
    })
    return config


DontCareSentinel = object()


class Message:
    def __init__(self, event: str, details: dict[str, object], room: Any = DontCareSentinel) -> None:
        self.event = event
        self.details = details
        self.room = room

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Message):
            return False
        if (self.room is DontCareSentinel) or (other.room is DontCareSentinel):
            return self.event == other.event and self.details == other.details
        else:
            return self.event == other.event and self.details == other.details and self.room == other.room

    def __repr__(self) -> str:
        if self.room is DontCareSentinel:
            return f"Message(event={self.event!r}, details={self.details!r})"
        else:
            return f"Message(event={self.event!r}, details={self.details!r}, room={self.room!r})"


class MockSocketIO():
    def __init__(self) -> None:
        self.sent: list[Message] = []

    def emit(self, event: str, details: dict[str, object], *, room: Any = None) -> None:
        self.sent.append(
            Message(event, details, room),
        )


def set_return(func: Any, return_value: Any) -> None:
    func.return_value = return_value


def set_lambda(func: Any, lambda_func: Any) -> None:
    func.side_effect = lambda_func
