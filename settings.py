from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

import env_bootstrap  # noqa: F401  — 加载项目根 .env（先于下方 getenv）


DEFAULT_API_KEY = "desktop-control-key"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_UI_MAX_DEPTH = 8
UI_MAX_DEPTH_MIN = 1
UI_MAX_DEPTH_MAX = 30


def default_ui_max_depth() -> int:
    """
    UIA 读树默认深度（``/ui/dom/read``、``/ui/widgets/*``、控件解析、OCR 裁剪等未传 ``max_depth`` 时）。

    环境变量 ``DESKTOP_UI_MAX_DEPTH``；无法解析时回退 ``DEFAULT_UI_MAX_DEPTH``；解析成功则 clamp 到 1–30。
    """
    raw = (os.getenv("DESKTOP_UI_MAX_DEPTH") or "").strip()
    if raw == "":
        v = DEFAULT_UI_MAX_DEPTH
    else:
        try:
            v = int(raw, 10)
        except ValueError:
            v = DEFAULT_UI_MAX_DEPTH
    return max(UI_MAX_DEPTH_MIN, min(UI_MAX_DEPTH_MAX, v))


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _parse_int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if raw == "":
        return default
    try:
        return int(raw, 10)
    except ValueError:
        return default


def _split_csv_env(name: str) -> List[str]:
    raw = os.getenv(name) or ""
    items = [s.strip() for s in raw.split(",")]
    return [s for s in items if s]


def _parse_float_env(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def tooling_api_base() -> str:
    """客户端脚本默认 API 根 URL（``DESKTOP_API_BASE``；未设时按 ``DESKTOP_HOST`` + ``DESKTOP_PORT`` 拼接）。"""
    explicit = (os.getenv("DESKTOP_API_BASE") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = (os.getenv("DESKTOP_HOST") or "").strip() or DEFAULT_HOST
    port = _parse_int_env("DESKTOP_PORT", DEFAULT_PORT)
    return f"http://{host}:{port}".rstrip("/")


def tooling_api_key() -> str:
    """客户端脚本默认 ``X-API-Key``（``DESKTOP_API_KEY``）。"""
    return (os.getenv("DESKTOP_API_KEY") or "").strip() or DEFAULT_API_KEY


def tooling_http_timeout_s(fallback: float) -> float:
    """
    ``DESKTOP_HTTP_TIMEOUT_S``；未设置时沿用各脚本原有 fallback（避免强行统一默认值）。
    """
    return _parse_float_env("DESKTOP_HTTP_TIMEOUT_S", fallback)


def tooling_ocr_lang(default: str = "chi_sim+eng") -> str:
    raw = (os.getenv("DESKTOP_OCR_LANG") or "").strip()
    return raw or default


@dataclass(frozen=True)
class Settings:
    api_keys: List[str]
    host: str
    port: int
    log_level: str
    allow_insecure_default_key: bool
    expose_debug_routes: bool

    @staticmethod
    def from_env() -> "Settings":
        keys = _split_csv_env("DESKTOP_API_KEYS")
        if not keys:
            key = (os.getenv("DESKTOP_API_KEY") or "").strip() or DEFAULT_API_KEY
            keys = [key]

        host = (os.getenv("DESKTOP_HOST") or "").strip() or DEFAULT_HOST
        port = _parse_int_env("DESKTOP_PORT", DEFAULT_PORT)
        log_level = (os.getenv("DESKTOP_LOG_LEVEL") or "").strip() or DEFAULT_LOG_LEVEL
        allow_insecure_default_key = _parse_bool_env("DESKTOP_ALLOW_INSECURE_DEFAULT_KEY", default=False)
        expose_debug_routes = _parse_bool_env("DESKTOP_EXPOSE_DEBUG_ROUTES", default=False)

        return Settings(
            api_keys=keys,
            host=host,
            port=port,
            log_level=log_level.upper(),
            allow_insecure_default_key=allow_insecure_default_key,
            expose_debug_routes=expose_debug_routes,
        )

