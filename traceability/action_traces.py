from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

TRACE_SCHEMA_VERSION = "action_trace.v1"

_TRACE_FIELDS = (
    "ts",
    "trace_id",
    "endpoint",
    "mode",
    "actor",
    "api_key_sha256_8",
    "hwnd",
    "stable_id",
    "resolved",
    "resolved_by",
    "verified",
    "verify_reason",
    "duration_ms",
    "success",
    "error_code",
)


def new_trace_id() -> str:
    # act_<epoch_ms>_<rand4>
    epoch_ms = int(time.time() * 1000)
    rand4 = secrets.token_hex(2)  # 4 hex chars
    return f"act_{epoch_ms}_{rand4}"


def _today_filename_utc() -> str:
    # YYYY-MM-DD.jsonl (UTC) to avoid local timezone ambiguity
    d = datetime.now(timezone.utc).date().isoformat()
    return f"{d}.jsonl"


def _normalize_trace_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize to a stable schema to avoid field drift across versions.
    """
    normalized: Dict[str, Any] = {"schema_version": TRACE_SCHEMA_VERSION}
    for key in _TRACE_FIELDS:
        normalized[key] = event.get(key)
    if not normalized["ts"]:
        normalized["ts"] = datetime.now(timezone.utc).isoformat()
    return normalized


def append_trace_event(event: Dict[str, Any], *, base_dir: str = "updates/traces") -> Optional[str]:
    """
    Append one JSON line to updates/traces/YYYY-MM-DD.jsonl.
    Returns the written file path on success; returns None on failure (never raises).
    """
    try:
        os.makedirs(base_dir, exist_ok=True)
        path = os.path.join(base_dir, _today_filename_utc())
        line = json.dumps(_normalize_trace_event(event), ensure_ascii=False, separators=(",", ":"))
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return path
    except Exception:
        return None

