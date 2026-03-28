from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


def _iter_symbol_spaces(auto: Any) -> List[Tuple[str, Any]]:
    spaces: List[Tuple[str, Any]] = [("module", auto)]
    for attr in ("automationClient", "_automationClient", "UIAutomationCore"):
        obj = getattr(auto, attr, None)
        if obj is not None:
            spaces.append((attr, obj))
    return spaces


def _pick_int_symbol(
    auto: Any, preferred_names: List[str], *, contains_all: Optional[List[str]] = None
) -> Tuple[Optional[int], Optional[str], List[str], Optional[str]]:
    candidates: List[str] = []
    selected_space: Optional[str] = None

    for space_name, space_obj in _iter_symbol_spaces(auto):
        for n in preferred_names:
            if hasattr(space_obj, n):
                v = getattr(space_obj, n)
                if isinstance(v, int):
                    return int(v), n, [f"{space_name}.{n}"], space_name

    contains_all = [t.lower() for t in (contains_all or [])]
    for space_name, space_obj in _iter_symbol_spaces(auto):
        names = dir(space_obj)
        for n in names:
            low = n.lower()
            if not all(token in low for token in contains_all):
                continue
            v = getattr(space_obj, n, None)
            if isinstance(v, int):
                candidates.append(f"{space_name}.{n}")

    if candidates:
        chosen = sorted(candidates)[0]
        space, name = chosen.split(".", 1)
        space_obj = dict(_iter_symbol_spaces(auto)).get(space, auto)
        return int(getattr(space_obj, name)), name, sorted(candidates)[:30], space
    return None, None, [], selected_space


def _pick_callable_symbol_strict(
    auto: Any, preferred_names: List[str]
) -> Tuple[Optional[Callable[..., Any]], Optional[str], List[str], Optional[str]]:
    candidates: List[str] = []
    selected_space: Optional[str] = None

    for space_name, space_obj in _iter_symbol_spaces(auto):
        for n in preferred_names:
            fn = getattr(space_obj, n, None)
            if callable(fn):
                return fn, n, [f"{space_name}.{n}"], space_name

    return None, None, candidates, selected_space


def resolve_invoke_event_id(auto: Any) -> Dict[str, Any]:
    preferred = [
        "UIA_Invoke_InvokedEventId",
        "Invoke_InvokedEventId",
        "InvokeInvokedEventId",
    ]
    value, selected_name, candidates, selected_space = _pick_int_symbol(auto, preferred, contains_all=["invoke", "event", "id"])
    return {
        "value": value,
        "selected_name": selected_name,
        "selected_space": selected_space,
        "candidates": candidates,
    }


def resolve_value_property_id(auto: Any) -> Dict[str, Any]:
    preferred = [
        "UIA_ValueValuePropertyId",
        "ValueValuePropertyId",
        "UIA_Value_PropertyId",
    ]
    value, selected_name, candidates, selected_space = _pick_int_symbol(auto, preferred, contains_all=["value", "property", "id"])
    return {
        "value": value,
        "selected_name": selected_name,
        "selected_space": selected_space,
        "candidates": candidates,
    }


def resolve_pump_fn(auto: Any) -> Dict[str, Any]:
    # Pump must be strict whitelist only. Do NOT fuzzy-match by "message"/"wait",
    # otherwise methods like MessageBox/SendMessage are incorrectly chosen.
    preferred = [
        "PumpWaitingMessages",
        "PumpMessages",
    ]
    fn, selected_name, candidates, selected_space = _pick_callable_symbol_strict(auto, preferred)
    return {
        "value": fn,
        "selected_name": selected_name,
        "selected_space": selected_space,
        "candidates": candidates,
    }

