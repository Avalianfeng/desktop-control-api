from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request


def wants_raw_response(request: Request) -> bool:
    v = (request.headers.get("X-Response-Mode") or "").strip().lower()
    if v == "raw":
        return True
    raw_q = (request.query_params.get("raw") or "").strip()
    return raw_q == "1"


def ok(*, data: Any, trace_id: Optional[str] = None) -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "trace_id": trace_id}


def fail(
    *,
    code: str,
    message: str,
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    details: Any = None,
) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if request_id is not None:
        err["request_id"] = request_id
    if details is not None:
        err["details"] = details
    return {"success": False, "data": None, "error": err, "trace_id": trace_id}

