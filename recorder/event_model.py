from __future__ import annotations

from typing import Any, Dict


def build_record(
    event_type: str,
    *,
    ts: str,
    delay_ms: int,
    window: Dict[str, Any],
    target: Dict[str, Any],
    selector: Dict[str, Any],
    version: str = "1.8.6",
) -> Dict[str, Any]:
    return {
        "ts": ts,
        "delay_ms": int(delay_ms) if delay_ms is not None else 0,
        "event": str(event_type),
        "window": dict(window),
        "target": dict(target),
        "selector": dict(selector),
        "version": str(version),
    }

