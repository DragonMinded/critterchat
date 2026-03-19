from enum import StrEnum
from typing import Literal, Type, TypeVar, overload


EnumT = TypeVar("EnumT", bound=StrEnum)


@overload
def coerce_enum(enum: Type[EnumT], value: object) -> EnumT | None: ...


@overload
def coerce_enum(enum: Type[EnumT], value: object, default: EnumT) -> EnumT: ...


@overload
def coerce_enum(enum: Type[EnumT], value: object, default: Literal[None]) -> EnumT | None: ...


def coerce_enum(enum: Type[EnumT], value: object, default: EnumT | None = None) -> EnumT | None:
    if not value:
        return default

    if not isinstance(value, str):
        return default

    try:
        return enum(value)
    except ValueError:
        return default
