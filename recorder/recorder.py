from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from recorder.control_validator import is_valid_control
from recorder.event_filter import current_intent_context, is_user_intent, should_record
from recorder.event_model import build_record
from recorder.event_sink import build_invoke_event, build_named_event, build_uia_event_raw, build_value_change_event
from recorder.selector_builder import build_selector, infer_role_and_dynamic_hint
from recorder.serializer import JsonlSerializer
from recorder.uia_com_bridge import UIAComBridge


class UIARecorder:
    """Minimal UIA event recorder for dev debugging."""

    def __init__(self, out_path: str, *, window_title: Optional[str] = None) -> None:
        self.out_path = out_path
        self.window_title = (window_title or "").strip() or None
        self.event_count = 0
        self.running = False

        self._serializer: Optional[JsonlSerializer] = None
        self._bridge: Optional[UIAComBridge] = None
        self._invoke_callbacks = 0
        self._value_callbacks = 0
        self._filtered_out = 0
        self._event_counts: Dict[str, int] = defaultdict(int)
        self._event_id_to_name: Dict[int, str] = {}
        self._property_id_to_name: Dict[int, str] = {}
        self._accepted = 0
        self._written = 0
        self._listen_root_mode: str = "unknown"
        self._start_summary_printed = False
        self._pump_error_printed = False
        self._last_accept_mono: Optional[float] = None
        self._dropped_by_type: Dict[str, int] = defaultdict(int)
        self._dropped_invalid_control = 0
        self._dropped_missing_window = 0
        self._dropped_scrollbar = 0
        self._dropped_passive_value_text = 0
        self._dropped_system_noise = 0

    def _diag(self, msg: str) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "component": "recorder",
            "msg": msg,
            "event_count": self.event_count,
            "invoke_callbacks": self._invoke_callbacks,
            "value_callbacks": self._value_callbacks,
            "filtered_out": self._filtered_out,
            "event_counts": dict(self._event_counts),
        }
        print(f"[Recorder][diag] {json.dumps(payload, ensure_ascii=False)}")

    def _diag_min(self, msg: str) -> None:
        """Minimal diagnostic output for humans (not structured)."""
        print(f"[Recorder] {msg}")

    @property
    def event_counts(self) -> Dict[str, int]:
        return dict(self._event_counts)

    @staticmethod
    def _safe_int(v: Any) -> Optional[int]:
        try:
            return int(v)
        except Exception:
            return None

    @staticmethod
    def _event_count_summary(counts: Dict[str, int], top_n: int = 8) -> str:
        if not counts:
            return "-"
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        return ", ".join(f"{k}={v}" for k, v in items)

    def start(self) -> None:
        if self.running:
            return
        self._serializer = JsonlSerializer(self.out_path)
        try:
            self._bridge = UIAComBridge(
                on_invoke=self._on_invoke,
                on_value_changed=self._on_property_changed,
                diag=self._diag_min,
                window_title=self.window_title,
            )
        except TypeError:
            # Test doubles / older signatures may not accept window_title.
            self._bridge = UIAComBridge(
                on_invoke=self._on_invoke,
                on_value_changed=self._on_property_changed,
                diag=self._diag_min,
            )
        started = self._bridge.start_handlers()
        details = self._bridge.details
        self._listen_root_mode = str(details.get("listen_root_mode") or "unknown")
        self._event_id_to_name = {
            int(v): k.replace("_event_id", "")
            for k, v in details.items()
            if k.endswith("_event_id") and isinstance(v, int) and v > 0
        }
        self._property_id_to_name = {
            int(v): k.replace("_property_id", "")
            for k, v in details.items()
            if k.endswith("_property_id") and isinstance(v, int) and v > 0
        }
        if started and not self._start_summary_printed:
            self._start_summary_printed = True
            self._diag_min(
                "started: "
                f"automation_mode={details.get('automation_mode')!r} "
                f"listen_root_mode={details.get('listen_root_mode')!r} "
                f"listen_root_name={details.get('listen_root_name')!r} "
                f"invoke={'ok' if details.get('invoke_registered', False) else 'fail'} "
                f"value={'ok' if details.get('value_registered', False) else 'skip'}"
            )
        else:
            self._diag_min(f"failed to start: reason={details.get('reason')!r}")
            if self._serializer is not None:
                self._serializer.close()
                self._serializer = None
            raise RuntimeError(f"Recorder bridge start failed: {details.get('reason')}")

        self.running = True
        self._diag_min(f"output={self.out_path}")

    def stop(self) -> None:
        if not self.running:
            return
        if self._bridge is not None:
            self._bridge.stop_handlers()
        if self._serializer:
            self._serializer.close()
        self._diag_min(
            f"recorder stopped; events={self.event_count} invoke_callbacks={self._invoke_callbacks} "
            f"value_callbacks={self._value_callbacks} filtered_out={self._filtered_out} "
            f"accepted={self._accepted} written={self._written} "
            f"dropped_by_type={dict(self._dropped_by_type)} dropped_invalid_control={self._dropped_invalid_control} "
            f"dropped_missing_window={self._dropped_missing_window} "
            f"dropped_scrollbar={self._dropped_scrollbar} dropped_passive_value_text={self._dropped_passive_value_text} "
            f"dropped_system_noise={self._dropped_system_noise} "
            f"event_counts={self._event_count_summary(self._event_counts)}"
        )
        self.running = False

    def run_until_interrupt(self, *, stop_file: Optional[str] = None, poll_interval_s: float = 0.2) -> int:
        self.start()
        stop_path = Path(stop_file) if stop_file else None
        try:
            while True:
                if stop_path is not None and stop_path.exists():
                    self._diag_min("stop signal file detected")
                    break
                now = time.perf_counter()
                if self._bridge is not None and self._bridge.started:
                    try:
                        self._bridge.pump(timeout_s=max(0.01, poll_interval_s))
                    except Exception as exc:
                        if not self._pump_error_printed:
                            self._pump_error_printed = True
                            self._diag_min(f"pump error: {type(exc).__name__}: {exc}")
                else:
                    # start() raises when bridge fails; keep loop simple.
                    pass
                time.sleep(max(0.05, poll_interval_s))
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
        return int(self.event_count)

    def _passes_window_filter(self, event: Dict[str, Any]) -> bool:
        if not self.window_title:
            return True
        # If we already subscribe to a specific window root, don't double-filter by title.
        # UIA events may carry empty/unstable window titles for child elements.
        if self._listen_root_mode == "window_title":
            return True
        title = str(event.get("window") or "")
        return self.window_title.casefold() in title.casefold()

    def _emit(self, raw_event: Dict[str, Any]) -> None:
        et = str(raw_event.get("event") or "")
        if not should_record(raw_event, debug=False):
            self._dropped_by_type[et or ""] += 1
            return

        control = raw_event.get("control") or {}
        if not isinstance(control, dict) or not is_valid_control(control):
            self._dropped_invalid_control += 1
            return

        window = raw_event.get("window") or {}
        title = ""
        if isinstance(window, dict):
            title = str(window.get("title") or "").strip()
        if not title:
            self._dropped_missing_window += 1
            return

        # Intent gate: drop non-user-intent events before delay calculation.
        ctx = current_intent_context()
        ok_intent, reason = is_user_intent(raw_event, ctx=ctx)
        if not ok_intent:
            if reason == "scrollbar":
                self._dropped_scrollbar += 1
            elif reason == "passive_value_text":
                self._dropped_passive_value_text += 1
            elif reason == "system_noise":
                self._dropped_system_noise += 1
            else:
                self._dropped_by_type[et or ""] += 1
            return

        if not self._passes_window_filter({"window": title}):
            self._filtered_out += 1
            return

        now_mono = time.monotonic()
        if self._last_accept_mono is None:
            delay_ms = 0
        else:
            delay_ms = max(0, int((now_mono - self._last_accept_mono) * 1000))
        self._last_accept_mono = now_mono

        target = {
            "name": str(control.get("name") or ""),
            "automation_id": str(control.get("automation_id") or ""),
            "control_type": str(control.get("control_type") or ""),
            "role": str(control.get("role") or ""),
        }
        role, dynamic_hint = infer_role_and_dynamic_hint(target)
        target["role"] = role
        if dynamic_hint:
            target["dynamic_hint"] = True
        selector = build_selector(target)
        record = build_record(et, ts=str(raw_event.get("ts") or ""), delay_ms=delay_ms, window=window, target=target, selector=selector, version="1.8.6")

        if self._serializer is not None:
            self._accepted += 1
            self._serializer.append(record)
            self._written += 1
            self.event_count += 1
            self._event_counts[et] += 1

    def _on_invoke(self, sender: Any, event_id: Any) -> None:  # noqa: ARG002
        try:
            self._invoke_callbacks += 1
            eid = self._safe_int(event_id)
            event_name = self._event_id_to_name.get(eid or -1)
            if event_name == "invoke":
                self._emit(build_invoke_event(sender))
            elif event_name in {"selection_item_selected", "menu_opened", "menu_closed", "structure_changed", "text_changed", "textedit_changed"}:
                normalized = (
                    "selection"
                    if event_name == "selection_item_selected"
                    else "menu_opened"
                    if event_name == "menu_opened"
                    else "menu_closed"
                    if event_name == "menu_closed"
                    else "structure_changed"
                    if event_name == "structure_changed"
                    else "text_change"
                )
                event = build_named_event(sender, normalized, event_id=eid)
                self._emit(event)
            else:
                self._emit(build_uia_event_raw(sender, event_id=eid if eid is not None else event_id))
        except Exception:
            return

    def _on_property_changed(self, sender: Any, property_id: Any, new_value: Any) -> None:
        try:
            self._value_callbacks += 1
            pid = self._safe_int(property_id)
            property_name = self._property_id_to_name.get(pid or -1)
            if property_name == "value":
                self._emit(build_value_change_event(sender, new_value))
            elif property_name == "toggle_state":
                event = build_named_event(sender, "toggle")
                event["property_id"] = str(pid) if pid is not None else str(property_id)
                event["value"] = str(new_value)
                self._emit(event)
            elif property_name == "expand_collapse_state":
                event = build_named_event(sender, "expand_collapse")
                event["property_id"] = str(pid) if pid is not None else str(property_id)
                event["value"] = str(new_value)
                self._emit(event)
            else:
                self._emit(build_uia_event_raw(sender, property_id=pid if pid is not None else property_id))
        except Exception:
            return

