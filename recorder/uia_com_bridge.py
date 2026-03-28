from __future__ import annotations

import ctypes
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


InvokeCallback = Callable[[Any, Any], None]
ValueChangedCallback = Callable[[Any, Any, Any], None]
DiagCallback = Callable[[str], None]

# Keep strong refs to COM objects/handlers to avoid GC edge-cases.
# Some UIA event deliveries can silently stop if handlers are collected.
_UIA_COM_KEEPALIVE: list[Any] = []


@dataclass
class StartResult:
    started: bool
    details: Dict[str, Any]


class _BackendProtocol:
    def start(
        self,
        *,
        on_invoke: InvokeCallback,
        on_value: ValueChangedCallback,
        diag: DiagCallback,
        window_title: Optional[str] = None,
    ) -> StartResult:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def pump(self, timeout_s: float = 0.05) -> None:
        raise NotImplementedError


class ComtypesUIABackend(_BackendProtocol):
    """Best-effort COM UIAutomation backend using comtypes."""

    def __init__(self) -> None:
        self._comtypes: Any = None
        self._uia: Any = None
        self._root: Any = None
        self._listen_root: Any = None
        self._event_handler: Any = None
        self._prop_handler: Any = None
        self._focus_handler: Any = None
        self._event_id: Optional[int] = None
        self._value_prop_id: Optional[int] = None
        self._selection_item_selected_event_id: Optional[int] = None
        self._menu_opened_event_id: Optional[int] = None
        self._menu_closed_event_id: Optional[int] = None
        self._structure_changed_event_id: Optional[int] = None
        self._focus_event_id: Optional[int] = None
        self._text_changed_event_id: Optional[int] = None
        self._textedit_changed_event_id: Optional[int] = None
        self._toggle_state_property_id: Optional[int] = None
        self._expand_collapse_state_property_id: Optional[int] = None
        self._tree_scope_subtree: Optional[int] = None
        self._sta_initialized = False
        self._focus_probe_logged = False
        self._invoke_seen = 0
        self._value_seen = 0

    def start(
        self,
        *,
        on_invoke: InvokeCallback,
        on_value: ValueChangedCallback,
        diag: DiagCallback,
        window_title: Optional[str] = None,
    ) -> StartResult:
        if sys.platform != "win32":
            return StartResult(started=False, details={"reason": "not_windows"})

        try:
            import comtypes  # type: ignore
            import comtypes.client  # type: ignore
        except Exception as exc:
            return StartResult(started=False, details={"reason": "comtypes_import_failed", "error": str(exc)})

        self._comtypes = comtypes
        try:
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as UIA  # type: ignore
        except Exception as exc:
            return StartResult(started=False, details={"reason": "uia_module_load_failed", "error": str(exc)})

        details: Dict[str, Any] = {
            "backend": "comtypes",
            "uia_module": "comtypes.gen.UIAutomationClient",
            "thread_register": threading.get_ident(),
        }

        # Ensure STA apartment for COM event callbacks.
        try:
            COINIT_APARTMENTTHREADED = 0x2
            hr = int(ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED))
            # S_OK(0) / S_FALSE(1) are both acceptable.
            details["coinit_hr"] = hr
            self._sta_initialized = hr in (0, 1)
        except Exception as exc:
            details["coinit_error"] = str(exc)
            self._sta_initialized = False
        if not self._sta_initialized:
            return StartResult(started=False, details={**details, "reason": "coinit_failed"})

        try:
            # Interface-only creation: avoids depending on ProgID registration.
            self._uia = comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
            details["automation_mode"] = "CUIAutomation(interface)"
            self._root = self._uia.GetRootElement()
        except Exception as exc:
            return StartResult(started=False, details={"reason": "uia_create_failed", "error": str(exc)})

        root_name = ""
        root_class = ""
        try:
            root_name = str(getattr(self._root, "CurrentName", "") or "")
        except Exception:
            root_name = ""
        try:
            root_class = str(getattr(self._root, "CurrentClassName", "") or "")
        except Exception:
            root_class = ""
        details["root_name"] = root_name
        details["root_class"] = root_class
        rn = root_name.strip().lower()
        rc = root_class.strip().lower()
        details["root_is_desktop"] = (
            rn == "desktop"
            or rn.startswith("桌面")
            or rc in {"progman", "workerw", "#32769"}
        )

        # Default subscription root is desktop root.
        self._listen_root = self._root
        details["listen_root_mode"] = "desktop"
        details["listen_root_name"] = root_name
        details["listen_root_class"] = root_class

        # If user provided a window title, try to subscribe to that top-level window directly.
        # This reduces noise and avoids cases where some providers don't bubble events to desktop.
        wtitle = (window_title or "").strip()
        if wtitle:
            try:
                cond = self._uia.CreatePropertyCondition(int(UIA.UIA_NamePropertyId), wtitle)
                candidate = self._root.FindFirst(int(UIA.TreeScope_Children), cond)
                if candidate is not None:
                    self._listen_root = candidate
                    details["listen_root_mode"] = "window_title"
                    try:
                        details["listen_root_name"] = str(getattr(candidate, "CurrentName", "") or "")
                    except Exception:
                        details["listen_root_name"] = ""
                    try:
                        details["listen_root_class"] = str(getattr(candidate, "CurrentClassName", "") or "")
                    except Exception:
                        details["listen_root_class"] = ""
                else:
                    details["listen_root_mode"] = "window_title_not_found"
            except Exception as exc:
                details["listen_root_mode"] = "window_title_error"
                details["listen_root_error"] = str(exc)

        self._event_id = int(getattr(UIA, "UIA_Invoke_InvokedEventId", 0) or 0) or None
        self._value_prop_id = int(getattr(UIA, "UIA_ValueValuePropertyId", 0) or 0) or None
        self._selection_item_selected_event_id = int(getattr(UIA, "UIA_SelectionItem_ElementSelectedEventId", 0) or 0) or None
        self._menu_opened_event_id = int(getattr(UIA, "UIA_MenuOpenedEventId", 0) or 0) or None
        self._menu_closed_event_id = int(getattr(UIA, "UIA_MenuClosedEventId", 0) or 0) or None
        self._structure_changed_event_id = int(getattr(UIA, "UIA_StructureChangedEventId", 0) or 0) or None
        self._focus_event_id = int(getattr(UIA, "UIA_AutomationFocusChangedEventId", 0) or 0) or None
        self._text_changed_event_id = int(getattr(UIA, "UIA_Text_TextChangedEventId", 0) or 0) or None
        self._textedit_changed_event_id = int(getattr(UIA, "UIA_TextEdit_TextChangedEventId", 0) or 0) or None
        self._toggle_state_property_id = int(getattr(UIA, "UIA_ToggleToggleStatePropertyId", 0) or 0) or None
        self._expand_collapse_state_property_id = int(getattr(UIA, "UIA_ExpandCollapseExpandCollapseStatePropertyId", 0) or 0) or None
        self._tree_scope_subtree = int(getattr(UIA, "TreeScope_Subtree", 0) or 0) or None

        details["invoke_event_id"] = self._event_id
        details["selection_item_selected_event_id"] = self._selection_item_selected_event_id
        details["menu_opened_event_id"] = self._menu_opened_event_id
        details["menu_closed_event_id"] = self._menu_closed_event_id
        details["structure_changed_event_id"] = self._structure_changed_event_id
        details["value_property_id"] = self._value_prop_id
        details["toggle_state_property_id"] = self._toggle_state_property_id
        details["expand_collapse_state_property_id"] = self._expand_collapse_state_property_id
        details["focus_event_id"] = self._focus_event_id
        details["text_changed_event_id"] = self._text_changed_event_id
        details["textedit_changed_event_id"] = self._textedit_changed_event_id
        details["tree_scope_subtree"] = self._tree_scope_subtree

        if not self._event_id or not self._tree_scope_subtree:
            return StartResult(started=False, details={**details, "reason": "missing_core_constants"})

        # Keep refs so COM callbacks don't get GC'd.
        backend_self = self
        event_ids_to_register = {
            "invoke": self._event_id,
            "selection_item_selected": self._selection_item_selected_event_id,
            "menu_opened": self._menu_opened_event_id,
            "menu_closed": self._menu_closed_event_id,
            "structure_changed": self._structure_changed_event_id,
            "text_changed": self._text_changed_event_id,
            "textedit_changed": self._textedit_changed_event_id,
        }
        value_like_event_ids = {int(v) for k, v in event_ids_to_register.items() if v and k in {"text_changed", "textedit_changed"}}

        def _safe_int(v: Any) -> Any:
            try:
                return int(v)
            except Exception:
                return str(v)

        class AutomationEventHandler(comtypes.COMObject):  # type: ignore
            _com_interfaces_ = [UIA.IUIAutomationEventHandler]

            def HandleAutomationEvent(self, sender, eventId):  # noqa: N802
                event_id = _safe_int(eventId)
                try:
                    backend_self._invoke_seen += 1
                    if backend_self._invoke_seen == 1:
                        sender_name = ""
                        try:
                            sender_name = str(getattr(sender, "CurrentName", "") or "")
                        except Exception:
                            sender_name = ""
                        diag(
                            "callback_invoke reached: "
                            f"thread={threading.get_ident()} eventId={event_id} sender_name={sender_name!r}"
                        )
                    if isinstance(event_id, int) and event_id in value_like_event_ids:
                        # Some apps emit text changed events instead of ValueValueProperty changes.
                        on_value(sender, eventId, None)
                    else:
                        on_invoke(sender, eventId)
                except Exception as exc:
                    diag(f"callback_invoke handler_error: {type(exc).__name__}: {exc}")
                return 0

        class PropertyChangedEventHandler(comtypes.COMObject):  # type: ignore
            _com_interfaces_ = [UIA.IUIAutomationPropertyChangedEventHandler]

            def HandlePropertyChangedEvent(self, sender, propertyId, newValue):  # noqa: N802
                prop_id = _safe_int(propertyId)
                try:
                    backend_self._value_seen += 1
                    if backend_self._value_seen == 1:
                        diag(f"callback_value reached: thread={threading.get_ident()} propertyId={prop_id}")
                    on_value(sender, propertyId, newValue)
                except Exception as exc:
                    diag(f"callback_value handler_error: {type(exc).__name__}: {exc}")
                return 0

        class FocusChangedEventHandler(comtypes.COMObject):  # type: ignore
            _com_interfaces_ = [UIA.IUIAutomationFocusChangedEventHandler]

            def HandleFocusChangedEvent(self, sender):  # noqa: N802
                if not backend_self._focus_probe_logged:
                    backend_self._focus_probe_logged = True
                    diag(f"callback_focus reached: thread={threading.get_ident()}")
                # Focus callback used as probe; no emit to JSONL to avoid schema expansion.
                return 0

        self._event_handler = AutomationEventHandler()
        self._prop_handler = PropertyChangedEventHandler()
        self._focus_handler = FocusChangedEventHandler()
        _UIA_COM_KEEPALIVE.extend([self._uia, self._root, self._listen_root, self._event_handler, self._prop_handler, self._focus_handler])
        details["keepalive_pool_size"] = len(_UIA_COM_KEEPALIVE)

        event_registration: Dict[str, Dict[str, Any]] = {}
        for event_name, event_id in event_ids_to_register.items():
            if not event_id:
                event_registration[event_name] = {"registered": False, "error": "missing_event_id"}
                continue
            try:
                self._uia.AddAutomationEventHandler(
                    int(event_id),
                    self._listen_root,
                    self._tree_scope_subtree,
                    None,
                    self._event_handler,
                )
                event_registration[event_name] = {"registered": True}
            except Exception as exc:
                event_registration[event_name] = {"registered": False, "error": str(exc)}
        details["event_registration"] = event_registration
        details["invoke_registered"] = bool(event_registration.get("invoke", {}).get("registered"))
        details["text_event_registered"] = bool(
            event_registration.get("text_changed", {}).get("registered")
            or event_registration.get("textedit_changed", {}).get("registered")
        )
        if not details["invoke_registered"]:
            reason = event_registration.get("invoke", {}).get("error") or "invoke_register_failed"
            return StartResult(started=False, details={**details, "reason": "invoke_register_failed", "error": reason})

        # FocusChanged probe: optional diagnostic hook to verify callback pipeline.
        focus_registered = False
        focus_error = None
        if self._focus_event_id:
            try:
                # FocusChanged uses dedicated API in UIAutomation.
                if hasattr(self._uia, "AddFocusChangedEventHandler"):
                    self._uia.AddFocusChangedEventHandler(None, self._focus_handler)
                    focus_registered = True
                else:
                    focus_error = "AddFocusChangedEventHandler not available on this interface"
            except Exception as exc:
                focus_error = str(exc)
        details["focus_registered"] = focus_registered
        if focus_error:
            details["focus_register_error"] = focus_error

        # PropertyChanged is optional; failure should not block invoke recording.
        property_ids_to_register = {
            "value": self._value_prop_id,
            "toggle_state": self._toggle_state_property_id,
            "expand_collapse_state": self._expand_collapse_state_property_id,
        }
        property_registration: Dict[str, Dict[str, Any]] = {}
        valid_props = [int(pid) for pid in property_ids_to_register.values() if pid]
        if valid_props:
            try:
                from ctypes import c_int

                props = (c_int * len(valid_props))(*valid_props)
                if hasattr(self._uia, "AddPropertyChangedEventHandlerNativeArray"):
                    self._uia.AddPropertyChangedEventHandlerNativeArray(
                        self._listen_root,
                        self._tree_scope_subtree,
                        None,
                        self._prop_handler,
                        props,
                        len(valid_props),
                    )
                elif hasattr(self._uia, "AddPropertyChangedEventHandler"):
                    self._uia.AddPropertyChangedEventHandler(
                        self._listen_root,
                        self._tree_scope_subtree,
                        None,
                        self._prop_handler,
                        props,
                    )
                for prop_name, prop_id in property_ids_to_register.items():
                    if prop_id:
                        property_registration[prop_name] = {"registered": True}
                    else:
                        property_registration[prop_name] = {"registered": False, "error": "missing_property_id"}
            except Exception as exc:
                for prop_name, prop_id in property_ids_to_register.items():
                    if prop_id:
                        property_registration[prop_name] = {"registered": False, "error": str(exc)}
                    else:
                        property_registration[prop_name] = {"registered": False, "error": "missing_property_id"}
        else:
            for prop_name in property_ids_to_register:
                property_registration[prop_name] = {"registered": False, "error": "missing_property_id"}

        details["property_registration"] = property_registration
        details["value_registered"] = bool(property_registration.get("value", {}).get("registered"))
        if not details["value_registered"]:
            details["value_register_error"] = property_registration.get("value", {}).get("error")

        details["diag_counters"] = {"invoke_seen": self._invoke_seen, "value_seen": self._value_seen}
        return StartResult(started=True, details=details)

    def stop(self) -> None:
        try:
            if self._uia is not None and self._listen_root is not None and self._event_handler is not None:
                if self._event_id:
                    try:
                        self._uia.RemoveAutomationEventHandler(self._event_id, self._listen_root, self._event_handler)
                    except Exception:
                        pass
                for text_event_id in (
                    self._selection_item_selected_event_id,
                    self._menu_opened_event_id,
                    self._menu_closed_event_id,
                    self._structure_changed_event_id,
                    self._text_changed_event_id,
                    self._textedit_changed_event_id,
                ):
                    if text_event_id:
                        try:
                            self._uia.RemoveAutomationEventHandler(text_event_id, self._listen_root, self._event_handler)
                        except Exception:
                            pass
                if self._focus_event_id:
                    try:
                        if hasattr(self._uia, "RemoveFocusChangedEventHandler") and self._focus_handler is not None:
                            self._uia.RemoveFocusChangedEventHandler(self._focus_handler)
                    except Exception:
                        pass
            if self._uia is not None and self._listen_root is not None and self._prop_handler is not None:
                try:
                    self._uia.RemovePropertyChangedEventHandler(self._listen_root, self._prop_handler)
                except Exception:
                    pass
        finally:
            if self._sta_initialized:
                try:
                    ctypes.windll.ole32.CoUninitialize()
                except Exception:
                    pass
                self._sta_initialized = False
            # Best-effort cleanup of keepalive pool to avoid unbounded growth in long dev sessions.
            try:
                for obj in (self._uia, self._root, self._listen_root, self._event_handler, self._prop_handler, self._focus_handler):
                    if obj in _UIA_COM_KEEPALIVE:
                        _UIA_COM_KEEPALIVE.remove(obj)
            except Exception:
                pass

    def pump(self, timeout_s: float = 0.05) -> None:
        if self._comtypes is None:
            return
        try:
            # Required for COM event dispatch on many environments.
            import comtypes.client  # type: ignore

            comtypes.client.PumpEvents(timeout_s)
        except Exception:
            return


class UIAComBridge:
    def __init__(
        self,
        *,
        on_invoke: InvokeCallback,
        on_value_changed: ValueChangedCallback,
        diag: DiagCallback,
        backend: Optional[_BackendProtocol] = None,
        window_title: Optional[str] = None,
    ) -> None:
        self._on_invoke = on_invoke
        self._on_value_changed = on_value_changed
        self._diag = diag
        self._backend: _BackendProtocol = backend or ComtypesUIABackend()
        self._started = False
        self._details: Dict[str, Any] = {}
        self._window_title = (window_title or "").strip() or None

    @property
    def details(self) -> Dict[str, Any]:
        return dict(self._details)

    @property
    def started(self) -> bool:
        return bool(self._started)

    def start_handlers(self) -> bool:
        try:
            result = self._backend.start(
                on_invoke=self._on_invoke,
                on_value=self._on_value_changed,
                diag=self._diag,
                window_title=self._window_title,
            )
        except TypeError:
            # Some test doubles/backends may not accept window_title.
            result = self._backend.start(
                on_invoke=self._on_invoke,
                on_value=self._on_value_changed,
                diag=self._diag,
            )
        self._started = bool(result.started)
        self._details = dict(result.details)
        return self._started

    def stop_handlers(self) -> None:
        self._backend.stop()
        self._started = False

    def pump(self, timeout_s: float = 0.05) -> None:
        self._backend.pump(timeout_s=timeout_s)

