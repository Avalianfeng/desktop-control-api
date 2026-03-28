from __future__ import annotations

import sys
import types

from controllers.keyboard import KeyboardController


def test_type_text_ascii_uses_write(monkeypatch) -> None:
    wrote: list[str] = []

    def fake_write(text: str, interval: float = 0.05) -> None:
        wrote.append(text)

    monkeypatch.setattr("controllers.keyboard.pyautogui.write", fake_write)
    monkeypatch.setattr("controllers.keyboard.pyautogui.hotkey", lambda *a, **k: None)

    k = KeyboardController()
    k.type_text("abc123", interval=0.01)
    assert wrote == ["abc123"]


def test_type_text_non_ascii_uses_clipboard(monkeypatch) -> None:
    copied: list[str] = []
    hotkeys: list[tuple] = []

    def fake_copy(t: str) -> None:
        copied.append(t)

    def fake_hotkey(*a, **k):
        hotkeys.append(tuple(a))

    clip = types.SimpleNamespace(copy=fake_copy)
    monkeypatch.setitem(sys.modules, "pyperclip", clip)
    monkeypatch.setattr("controllers.keyboard.pyautogui.write", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not write")))
    monkeypatch.setattr("controllers.keyboard.pyautogui.hotkey", fake_hotkey)

    k = KeyboardController()
    k.type_text("中文", interval=0.01)
    assert copied == ["中文"]
    assert hotkeys and hotkeys[0][0] == "ctrl" and hotkeys[0][1] == "v"
