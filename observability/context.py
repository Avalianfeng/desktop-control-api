from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Optional


_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


def set_request_id(request_id: Optional[str]) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


@dataclass(frozen=True)
class TraceContext:
    trace_id: Optional[str]
    span_id: Optional[str]

