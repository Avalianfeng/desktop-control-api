from __future__ import annotations

import re


_DIGIT_RE = re.compile(r"^\d$")


def normalize_label(text: str, *, control_type: str = "") -> str:
    t = (text or "").strip()
    if not t:
        return ""

    # digits
    if _DIGIT_RE.match(t):
        return f"digit_{t}"

    # equals / submit
    if t in {"=", "等于"}:
        return "equals"

    # operators
    if t in {"+", "加"}:
        return "add"
    if t in {"-", "减"}:
        return "subtract"
    if t in {"×", "*", "乘"}:
        return "multiply"
    if t in {"÷", "/", "除"}:
        return "divide"

    # window controls (best-effort; multilingual partials)
    if "最小化" in t or t.lower() == "minimize":
        return "window_minimize"
    if "最大化" in t or t.lower() == "maximize":
        return "window_maximize"
    if "关闭" in t or t.lower() == "close":
        return "window_close"

    # fallback: stable-ish token
    # keep ASCII words/numbers/underscore, collapse others to underscore
    asciiish = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return asciiish or ""

