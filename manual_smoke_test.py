#!/usr/bin/env python3
"""
根目录手动冒烟测试：确认本地 Desktop Control API 核心能力可用。

用法（需先在本机启动服务：python server.py）::

    python manual_smoke_test.py

可在项目根 ``.env`` 中配置（与 test_client 相同）::

    DESKTOP_API_BASE / DESKTOP_API_KEY / DESKTOP_HTTP_TIMEOUT_S
仅通过 HTTP 验证；退出码 0 表示无硬失败项；WARN 不导致失败。

说明
    - 会真实调用截图与（可选）OCR，在 updates/screenshots/ 下产生 PNG；测试后可按需清理。
    - /readyz 依赖窗口枚举与 UIA；无桌面会话时可能 503。默认记为 WARN；加 --strict-readyz 则记为失败。
    - /ocr/read 依赖 Tesseract；未安装时默认 WARN；加 --strict-ocr 则记为失败。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

import env_bootstrap  # noqa: F401

from settings import tooling_api_base, tooling_api_key, tooling_http_timeout_s

DEFAULT_BASE = tooling_api_base()
DEFAULT_KEY = tooling_api_key()
TIMEOUT = tooling_http_timeout_s(30.0)


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


def _headers(api_key: str, json_ct: bool = True) -> Dict[str, str]:
    h = {"X-API-Key": api_key}
    if json_ct:
        h["Content-Type"] = "application/json"
    return h


def _json(resp: requests.Response) -> Dict[str, Any]:
    try:
        out = resp.json()
        return out if isinstance(out, dict) else {"_raw": out}
    except Exception:
        return {"_parse_error": (resp.text or "")[:500]}


def main() -> int:
    p = argparse.ArgumentParser(description="Desktop Control API 手动冒烟测试")
    p.add_argument("--base-url", default=DEFAULT_BASE, help="API 根 URL")
    p.add_argument("--api-key", default=DEFAULT_KEY, help="X-API-Key")
    p.add_argument(
        "--strict-readyz",
        action="store_true",
        help="/readyz 非 200 时计为失败（默认 WARN）",
    )
    p.add_argument(
        "--strict-ocr",
        action="store_true",
        help="OCR 失败时计为失败（默认未装 Tesseract 仅 WARN）",
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    key = args.api_key
    sess = _session()
    rows: List[Tuple[str, str, str]] = []  # (status, name, detail) status=OK|WARN|FAIL
    failures = 0

    def record(ok: bool, name: str, detail: str, *, soft: bool) -> None:
        nonlocal failures
        if ok:
            rows.append(("OK", name, detail))
            return
        if soft:
            rows.append(("WARN", name, detail))
            return
        rows.append(("FAIL", name, detail))
        failures += 1

    def get(path: str, *, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        return sess.get(f"{base}{path}", headers=headers, timeout=TIMEOUT)

    def post(path: str, body: Optional[Dict[str, Any]] = None) -> requests.Response:
        return sess.post(
            f"{base}{path}",
            headers=_headers(key),
            json=body if body is not None else {},
            timeout=TIMEOUT,
        )

    # 1) 健康（无需 Key）
    r = get("/health", headers={})
    j = _json(r)
    record(
        r.status_code == 200 and j.get("success") is True,
        "GET /health",
        f"status={r.status_code}",
        soft=False,
    )

    r = get("/livez", headers={})
    j = _json(r)
    record(
        r.status_code == 200 and j.get("success") is True,
        "GET /livez",
        f"status={r.status_code}",
        soft=False,
    )

    # 2) 鉴权
    r = get("/windows", headers=_headers("definitely-not-the-api-key"))
    record(
        r.status_code == 403,
        "auth invalid X-API-Key -> 403",
        f"status={r.status_code}",
        soft=False,
    )

    # 3) readiness
    r = get("/readyz", headers={})
    j = _json(r)
    ok_rz = r.status_code == 200 and j.get("success") is True
    record(
        ok_rz,
        "GET /readyz",
        f"status={r.status_code} error={j.get('error')}",
        soft=not args.strict_readyz,
    )

    # 4) 截图
    r = post("/screenshot", {})
    j = _json(r)
    path_full = (j.get("data") or {}).get("path")
    record(
        r.status_code == 200
        and j.get("success") is True
        and isinstance(path_full, str)
        and len(path_full) > 0,
        "POST /screenshot data.path 非空",
        f"path={path_full!r}",
        soft=False,
    )

    r = post("/screenshot/region", {"x": 0, "y": 0, "width": 32, "height": 32, "scale": 1.0})
    j = _json(r)
    reg_path = (j.get("data") or {}).get("path")
    record(
        r.status_code == 200
        and j.get("success") is True
        and isinstance(reg_path, str)
        and len(reg_path) > 0,
        "POST /screenshot/region data.path 非空",
        f"path={reg_path!r}",
        soft=False,
    )

    # 5) 窗口与 UI 只读
    r = get("/windows", headers=_headers(key, json_ct=False))
    j = _json(r)
    wins = (j.get("data") or {}).get("windows")
    record(
        r.status_code == 200 and j.get("success") is True and isinstance(wins, list),
        "GET /windows",
        f"count={len(wins) if isinstance(wins, list) else 'n/a'}",
        soft=False,
    )

    r = post("/ui/dom/read", {"max_depth": 4})
    j = _json(r)
    record(
        r.status_code in (200, 206) and j.get("success") is True,
        "POST /ui/dom/read",
        f"status={r.status_code}",
        soft=False,
    )

    r = post(
        "/ui/widgets/read",
        {"max_depth": 6, "include_text_widgets": True, "collapse_icons": True},
    )
    j = _json(r)
    data = j.get("data") or {}
    record(
        r.status_code in (200, 206) and j.get("success") is True and "widgets" in data,
        "POST /ui/widgets/read",
        f"status={r.status_code} widgets={len(data.get('widgets') or [])}",
        soft=False,
    )

    r = post("/ui/widgets/query", {"filters": {}, "limit": 3, "select": ["id", "role"]})
    j = _json(r)
    record(
        r.status_code in (200, 206) and j.get("success") is True,
        "POST /ui/widgets/query",
        f"status={r.status_code}",
        soft=False,
    )

    # 6) v1.9 OCR（使用刚生成的区域截图路径）
    ocr_path: Optional[str] = reg_path if isinstance(reg_path, str) else None
    if not ocr_path:
        ocr_path = path_full if isinstance(path_full, str) else None
    if ocr_path:
        r = post(
            "/ocr/read",
            {"image_path": ocr_path, "lang": "eng", "tesseract_config": "--psm 6"},
        )
        j = _json(r)
        err_code = (j.get("error") or {}).get("code") if isinstance(j.get("error"), dict) else None
        if r.status_code == 200 and j.get("success"):
            lines = (j.get("data") or {}).get("lines")
            record(
                isinstance(lines, list),
                "POST /ocr/read",
                f"lines={len(lines) if isinstance(lines, list) else 0}",
                soft=False,
            )
        elif r.status_code == 503 and err_code == "tesseract_not_found":
            record(
                False,
                "POST /ocr/read",
                "tesseract_not_found（请安装 Tesseract 并加入 PATH）",
                soft=not args.strict_ocr,
            )
        else:
            record(
                False,
                "POST /ocr/read",
                f"status={r.status_code} error={j.get('error')}",
                soft=not args.strict_ocr,
            )
    else:
        record(False, "POST /ocr/read", "无截图 path 可测", soft=False)

    # 7) metrics
    r = get("/metrics", headers={})
    j = _json(r)
    if r.status_code == 200 and j.get("success") is True:
        record(True, "GET /metrics", "ok", soft=False)
    else:
        record(False, "GET /metrics", f"status={r.status_code}（可能未装 prometheus_client）", soft=True)

    print(f"API: {base}\n")
    for st, name, detail in rows:
        print(f"  [{st:4}] {name}: {detail}")
    print()
    if failures:
        print(f"失败 {failures} 项（见 FAIL）。修正服务、依赖或去掉 --strict-* 后重试。")
        return 1
    print("通过：无 FAIL。若存在 WARN，为环境或可选依赖限制。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
