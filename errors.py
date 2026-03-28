from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    cause: Optional[BaseException] = None
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

