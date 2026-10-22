"""Typed persistence for domain dataclasses on top of `db.records` (encode to JSON, decode back by type hints)."""

import dataclasses
import types
import typing
from datetime import date, datetime
from typing import Any

from pulse.core import db


def encode(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: encode(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, list | tuple):
        return [encode(x) for x in obj]
    return obj


def decode(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        inner = [a for a in typing.get_args(tp) if a is not type(None)]
        return decode(inner[0], value) if len(inner) == 1 else value
    if origin is tuple:
        item = typing.get_args(tp)[0]
        return tuple(decode(item, v) for v in value)
    if origin is typing.Literal:
        return value
    if tp is datetime:
        return datetime.fromisoformat(value)
    if tp is date:
        return date.fromisoformat(value)
    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        hints = typing.get_type_hints(tp)
        return tp(**{f.name: decode(hints[f.name], value.get(f.name)) for f in dataclasses.fields(tp)})
    return value


def _at(obj: Any, attr: str | None) -> str | None:
    if not attr:
        return None
    v = getattr(obj, attr)
    return v.isoformat() if isinstance(v, datetime | date) else None


def save(kind: str, items: list[Any], *, key: str = "id", at: str | None = None) -> int:
    return db.replace_kind(kind, ((str(getattr(i, key)), _at(i, at), encode(i)) for i in items))


def merge(kind: str, items: list[Any], *, key: str = "id", at: str | None = None) -> int:
    return db.upsert(kind, ((str(getattr(i, key)), _at(i, at), encode(i)) for i in items))


def load[T](kind: str, cls: type[T]) -> list[T]:
    return [typing.cast(T, decode(cls, p)) for p in db.load(kind)]
