from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from dom.semantic import build_semantic_dom
from engines.desktop_dom_engine import DesktopDOMEngine
from models.ui_dom import DesktopDOMResponse, UIReadOptions
from sources.uia_source import UIASource


@dataclass
class UIReadResult:
    payload: DesktopDOMResponse
    partial: bool


class UIReadController:
    """Controller-level scheduler for desktop DOM read."""

    def __init__(self):
        self.uia_source = UIASource()
        self.engine = DesktopDOMEngine()

    def read_dom(self, window_title: Optional[str], options: UIReadOptions, window_hwnd: Optional[int] = None) -> UIReadResult:
        snapshot = self.uia_source.read_window(window_title=window_title, window_hwnd=window_hwnd)
        built = self.engine.build(snapshot, options)
        payload = built.response
        if options.include_semantic:
            payload.semantic = build_semantic_dom(
                payload.dom,
                include_text_labels=options.semantic_include_text_labels,
            )
        else:
            payload.semantic = None
        return UIReadResult(payload=payload, partial=built.truncated)
