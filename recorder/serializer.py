from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import time


class JsonlSerializer:
    """Append-only JSONL writer for recorder events."""

    def __init__(self, out_path: str, *, flush_every: int = 25, flush_interval_s: float = 0.5):
        self.out_path = str(out_path)
        p = Path(self.out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.out_path, "a", encoding="utf-8", newline="\n")
        self._flush_every = max(1, int(flush_every))
        self._flush_interval_s = max(0.0, float(flush_interval_s))
        self._pending = 0
        self._last_flush = time.monotonic()

    def append(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        self._fp.write(line + "\n")
        self._pending += 1
        now = time.monotonic()
        if self._pending >= self._flush_every or (self._flush_interval_s > 0 and (now - self._last_flush) >= self._flush_interval_s):
            self._fp.flush()
            self._pending = 0
            self._last_flush = now

    def close(self) -> None:
        try:
            try:
                self._fp.flush()
            except Exception:
                pass
            self._fp.close()
        except Exception:
            pass

