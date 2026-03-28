from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


DEFAULT_API_KEY = "desktop-control-key"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_LOG_LEVEL = "INFO"


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


@dataclass(frozen=True)
class Settings:
    api_keys: List[str]
    host: str
    port: int
    log_level: str
    allow_insecure_default_key: bool

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

        return Settings(
            api_keys=keys,
            host=host,
            port=port,
            log_level=log_level.upper(),
            allow_insecure_default_key=allow_insecure_default_key,
        )

