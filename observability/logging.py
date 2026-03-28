from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import traceback
from typing import Any, Dict, Optional

from observability.context import get_request_id

try:
    from opentelemetry import trace as _otel_trace  # type: ignore
except Exception:  # pragma: no cover
    _otel_trace = None  # type: ignore


SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "x-api-key",
}


def _iso_utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _safe_json(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return repr(obj)


def _redact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        lk = str(k).lower()
        if lk in SENSITIVE_KEYS:
            out[k] = "[REDACTED]"
        else:
            out[k] = _safe_json(v)
    return out


def _current_trace_ids() -> Dict[str, Optional[str]]:
    if _otel_trace is None:
        return {"trace_id": None, "span_id": None}
    span = _otel_trace.get_current_span()
    ctx = span.get_span_context() if span is not None else None
    if ctx is None or not getattr(ctx, "is_valid", False):
        return {"trace_id": None, "span_id": None}
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }


class ObservabilityFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        rid = get_request_id()
        if not hasattr(record, "request_id"):
            record.request_id = rid
        ids = _current_trace_ids()
        if not hasattr(record, "trace_id"):
            record.trace_id = ids["trace_id"]
        if not hasattr(record, "span_id"):
            record.span_id = ids["span_id"]
        record.service = getattr(record, "service", os.getenv("OTEL_SERVICE_NAME") or "desktop-control-api")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "ts": _iso_utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": getattr(record, "service", None),
            "request_id": getattr(record, "request_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
        }

        extras: Dict[str, Any] = {}
        for k, v in record.__dict__.items():
            if k in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                continue
            if k in base:
                continue
            extras[k] = v
        if extras:
            base.update(_redact_dict(extras))

        if record.exc_info:
            et, ev, tb = record.exc_info
            base["error"] = {
                "type": getattr(et, "__name__", str(et)),
                "message": str(ev),
                "stack": "".join(traceback.format_exception(et, ev, tb)),
            }
        return json.dumps(base, ensure_ascii=False, separators=(",", ":"))


def configure_logging(*, level: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ObservabilityFilter())
    root.addHandler(handler)


def log_extra(fields: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if fields:
        merged.update(fields)
    merged.update(kwargs)
    return merged

