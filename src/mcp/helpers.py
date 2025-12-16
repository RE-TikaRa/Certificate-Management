from __future__ import annotations

from typing import Literal, cast

Transport = Literal["stdio", "sse", "streamable-http"]


def to_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def safe_int(value: str | None, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        num = int(value) if value is not None else default
    except Exception:
        num = default
    if min_value is not None:
        num = max(min_value, num)
    if max_value is not None:
        num = min(max_value, num)
    return num


def parse_transport(raw: str | None, default: Transport = "stdio") -> Transport:
    if raw not in ("stdio", "sse", "streamable-http"):
        return default
    return cast(Transport, raw)
