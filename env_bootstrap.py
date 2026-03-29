"""
在任意 ``os.getenv`` / ``Settings.from_env()`` 之前加载项目根目录的 ``.env``。

用法：在入口模块最前面 ``import env_bootstrap``（或依赖 ``settings``，其会先行 import 本模块）。
``load_dotenv(..., override=False)``：已存在于操作系统环境中的变量不会被 .env 覆盖。
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_LOADED = False


def load_project_env() -> None:
    """从项目根 ``.env`` 加载环境变量（幂等，缺文件或缺 python-dotenv 时静默跳过）。"""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    if not _ENV_PATH.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_ENV_PATH, override=False)


def project_root() -> Path:
    return _PROJECT_ROOT


load_project_env()
