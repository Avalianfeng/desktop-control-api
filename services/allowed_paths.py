from __future__ import annotations

from pathlib import Path
from typing import Optional

from errors import ApiError


def resolve_ocr_image_path(image_path: str, *, cwd: Optional[Path] = None) -> Path:
    """
    将 image_path 解析为绝对路径，且必须位于 cwd（默认进程工作目录）之下。
    禁止通过 .. 或符号链接跳出该根目录。
    """
    base = (cwd or Path.cwd()).resolve()
    raw = (image_path or "").strip()
    if not raw:
        raise ApiError(
            status_code=400,
            code="ocr_path_invalid",
            message="image_path 不能为空",
        )

    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else (base / candidate)).resolve()

    try:
        resolved.relative_to(base)
    except ValueError:
        raise ApiError(
            status_code=400,
            code="ocr_path_not_allowed",
            message="image_path 必须位于服务进程工作目录内",
            details={"cwd": str(base), "resolved": str(resolved)},
        )

    if not resolved.is_file():
        raise ApiError(
            status_code=404,
            code="ocr_image_not_found",
            message=f"图像文件不存在：{resolved}",
            details={"path": str(resolved)},
        )

    return resolved
