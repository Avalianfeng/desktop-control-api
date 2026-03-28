from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class WindowSelector:
    title: str
    hwnd: int = 0
    class_name: str = ""


@dataclass(frozen=True)
class ResolvedControl:
    sender: Any
    selector: Dict[str, Any]
    window: WindowSelector


def resolve(*, window: WindowSelector, selector: Dict[str, Any]) -> Optional[ResolvedControl]:
    """v2.0 placeholder: resolve selector to a UIA control."""
    raise NotImplementedError("v2.0: selector resolver not implemented")

