from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from runtime.selector_resolver import ResolvedControl


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    reason: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


def invoke(ctrl: ResolvedControl) -> ActionResult:
    """v2.0 placeholder: invoke a resolved control."""
    raise NotImplementedError("v2.0: action executor not implemented")


def set_value(ctrl: ResolvedControl, value: str) -> ActionResult:
    """v2.0 placeholder: set value on a resolved control."""
    raise NotImplementedError("v2.0: action executor not implemented")

