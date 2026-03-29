"""
真实窗口回归：UIA bounds ↔ 裁剪 PNG 对齐 + 重复 OCR 耗时与缓存启发式。

人类交互验收请用根目录 ``manual_ocr_inspector.py``（选窗/选控件/UIA 与 OCR 对比），勿依赖本用例。

前置::

    RUN_DESKTOP_INTEGRATION_TESTS=1、RUN_OCR_WINDOW_TESTS=1、Tesseract、匹配标题的窗口（见 DESKTOP_OCR_WINDOW_TITLE）

可选::

    DESKTOP_OCR_LANG、DESKTOP_OCR_REPEAT、DESKTOP_OCR_BOUNDS_TOLERANCE、DESKTOP_OCR_REQUIRE_SCALE=125|150

运行::

    pytest tests/integration/test_live_ocr_window_dpi.py -m ocr_window -s -v
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List

import pytest
import requests

from tests.integration.ocr_window_helpers import (
    bounds_image_delta_ratio,
    effective_ui_scale_percent,
    find_window_by_title,
    format_timing_report,
    parse_title_candidates,
    pick_widget_for_ocr_crop,
)

pytestmark = [
    pytest.mark.ocr_window,
    pytest.mark.skipif(sys.platform != "win32", reason="OCR 窗口集成仅针对 Windows"),
    pytest.mark.skipif(
        os.getenv("RUN_OCR_WINDOW_TESTS", "0").strip() != "1",
        reason="需设置 RUN_OCR_WINDOW_TESTS=1（并配合 RUN_DESKTOP_INTEGRATION_TESTS=1）",
    ),
]


def _require_scale_gate(scale_pct: int) -> None:
    req = (os.getenv("DESKTOP_OCR_REQUIRE_SCALE") or "").strip()
    if not req:
        return
    try:
        want = int(req)
    except ValueError:
        return
    if want not in (125, 150):
        return
    lo, hi = want - 3, want + 3
    if not (lo <= scale_pct <= hi):
        pytest.skip(f"当前缩放约 {scale_pct}%，与 DESKTOP_OCR_REQUIRE_SCALE={want} 不符（±3% 容差）")


@pytest.mark.ocr_window
def test_live_ocr_window_crop_dpi_alignment_and_repeat_timing(
    integration_base_url: str,
    integration_headers: Dict[str, str],
    integration_session: requests.Session,
    capsys,
) -> None:
    pytest.importorskip("pytesseract")
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Tesseract 不可用: {exc}")

    base = integration_base_url.rstrip("/")
    h = integration_headers
    s = integration_session

    scale_pct = effective_ui_scale_percent()
    _require_scale_gate(scale_pct)

    wr = s.get(f"{base}/windows", headers=h, timeout=15)
    assert wr.status_code == 200
    wj = wr.json()
    assert wj.get("success") is True
    data = wj.get("data") or {}
    windows: List[Dict[str, Any]] = data.get("windows") or []

    titles = parse_title_candidates()
    win = find_window_by_title(windows, titles)
    if win is None:
        pytest.skip(f"未找到标题匹配 {titles} 的窗口；请打开目标应用或设置 DESKTOP_OCR_WINDOW_TITLE")

    hwnd = int(win.get("hwnd") or 0)
    assert hwnd > 0
    title = str(win.get("title") or "")

    fr = s.post(f"{base}/windows/focus", headers=h, json={"hwnd": hwnd}, timeout=20)
    if fr.status_code != 200 or not (fr.json() or {}).get("success"):
        pytest.skip(f"无法聚焦窗口 hwnd={hwnd} title={title!r}：HTTP {fr.status_code}")

    qr = s.post(
        f"{base}/ui/widgets/query",
        headers=h,
        json={
            "window_hwnd": hwnd,
            "max_depth": 10,
            "filters": {},
            "limit": 80,
            "select": ["id", "role", "text", "normalized", "bounds"],
        },
        timeout=45,
    )
    assert qr.status_code in (200, 206), qr.text
    qj = qr.json()
    assert qj.get("success") is True
    qdata = qj.get("data") or {}
    widgets: List[Dict[str, Any]] = qdata.get("widgets") or []
    picked = pick_widget_for_ocr_crop(widgets)
    if picked is None:
        pytest.skip("未找到足够大的可裁剪控件；可换窗口或在交互模式下放大编辑区")

    wid = str(picked.get("id") or "")
    assert wid
    bounds = picked.get("bounds") or {}

    crop = s.post(
        f"{base}/screenshot/widget",
        headers=h,
        json={"id": wid, "target_hwnd": hwnd, "max_depth": 10},
        timeout=45,
    )
    assert crop.status_code == 200, crop.text
    cj = crop.json()
    assert cj.get("success") is True
    cd = cj.get("data") or {}
    iw = int(cd.get("image_width") or 0)
    ih = int(cd.get("image_height") or 0)
    assert iw > 0 and ih > 0, "响应应含 image_width/image_height（v1.9+ widget 裁剪）"

    rx, ry = bounds_image_delta_ratio(bounds, iw, ih)
    tol = float(os.getenv("DESKTOP_OCR_BOUNDS_TOLERANCE", "0.08"))
    assert rx <= tol and ry <= tol, (
        f"DPI/坐标对齐超出容差 {tol:.0%}: UIA bounds {bounds} vs 裁剪图 {iw}x{ih} "
        f"(Δx={rx:.1%} Δy={ry:.1%})，缩放约 {scale_pct}%"
    )

    lang = (os.getenv("DESKTOP_OCR_LANG") or "chi_sim+eng").strip() or "chi_sim+eng"
    repeat = max(2, min(12, int(os.getenv("DESKTOP_OCR_REPEAT", "4"))))

    body = {
        "id": wid,
        "target_hwnd": hwnd,
        "max_depth": 10,
        "lang": lang,
        "tesseract_config": "--psm 6",
    }

    times_ms: List[float] = []
    last_lines: List[Any] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        orr = s.post(f"{base}/ocr/read_widget", headers=h, json=body, timeout=120)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        times_ms.append(elapsed_ms)
        assert orr.status_code == 200, orr.text
        oj = orr.json()
        assert oj.get("success") is True
        od = oj.get("data") or {}
        last_lines = (od.get("ocr") or {}).get("lines") or []

    report = format_timing_report(times_ms, scale_pct=scale_pct)
    full_report = (
        f"\n=== OCR 窗口集成报告 ===\n"
        f"窗口: {title!r} hwnd={hwnd}\n"
        f"widget: id={wid!r} role={picked.get('role')!r} bounds={bounds}\n"
        f"裁剪: {iw}x{ih} capture_method={cd.get('capture_method')!r}\n"
        f"对齐: Δw/w={rx:.2%} Δh/h={ry:.2%} (tol={tol:.0%})\n"
        f"OCR lines(末次): {len(last_lines)}\n"
        f"{report}\n"
        f"========================\n"
    )
    with capsys.disabled():
        print(full_report)

    assert isinstance(last_lines, list)
