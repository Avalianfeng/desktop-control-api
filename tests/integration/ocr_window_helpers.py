"""
真实窗口 OCR / DPI 集成测试辅助函数（无业务逻辑依赖，便于人类阅读报告）。
"""

from __future__ import annotations

import os
import statistics
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple


def effective_ui_scale_percent() -> int:
    """
    主显示器逻辑缩放约略百分比（96 DPI = 100%，120≈125%，144≈150%）。
    仅 Windows 可靠；其它平台返回 100。
    """
    if sys.platform != "win32":
        return 100
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hdc = user32.GetDC(0)
        try:
            dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        finally:
            user32.ReleaseDC(0, hdc)
        return int(round(dpi_x * 100 / 96.0))
    except Exception:
        return 100


def parse_title_candidates() -> List[str]:
    raw = (os.getenv("DESKTOP_OCR_WINDOW_TITLE") or "").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return ["记事本", "Notepad", "计算器", "Calculator"]


def find_window_by_title(
    windows: Sequence[Dict[str, Any]], title_substrings: Sequence[str]
) -> Optional[Dict[str, Any]]:
    for sub in title_substrings:
        s_low = sub.casefold()
        for w in windows:
            title = str(w.get("title") or "")
            if s_low in title.casefold():
                return w
    return None


def pick_widget_for_ocr_crop(widgets: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    选择适合裁剪 OCR 的控件：面积足够大，优先 textbox / document / edit / text。
    """
    priority = ("textbox", "document", "edit", "text")

    def score(w: Dict[str, Any]) -> Tuple[int, int]:
        role = str(w.get("role") or "").casefold()
        role_hits = [i for i, r in enumerate(priority) if r in role]
        pr = min(role_hits) if role_hits else len(priority)
        b = w.get("bounds") or {}
        area = int(b.get("width") or 0) * int(b.get("height") or 0)
        return (pr, -area)

    candidates = []
    for w in widgets:
        b = w.get("bounds") or {}
        if int(b.get("width") or 0) < 24 or int(b.get("height") or 0) < 24:
            continue
        candidates.append(w)
    if not candidates:
        return None
    candidates.sort(key=score)
    return candidates[0]


def bounds_image_delta_ratio(bounds: Dict[str, Any], iw: int, ih: int) -> Tuple[float, float]:
    bw = max(int(bounds.get("width") or 0), 1)
    bh = max(int(bounds.get("height") or 0), 1)
    return abs(bw - iw) / bw, abs(bh - ih) / bh


def format_timing_report(times_ms: List[float], *, scale_pct: int) -> str:
    if not times_ms:
        return "无 OCR 计时样本。"
    n = len(times_ms)
    mean = statistics.mean(times_ms)
    stdev = statistics.stdev(times_ms) if n > 1 else 0.0
    lines = [
        f"系统缩放约 {scale_pct}%（LOGPIXELSX 推导）；OCR 样本 n={n}",
        f"  mean={mean:.1f} ms  stdev={stdev:.1f} ms  min={min(times_ms):.1f} ms  max={max(times_ms):.1f} ms",
    ]
    lines.append(cache_recommendation(times_ms, mean, stdev))
    return "\n".join(lines)


def cache_recommendation(times_ms: List[float], mean: float, stdev: float) -> str:
    """根据重复耗时给出是否值得加缓存的文字结论（启发式，非强制架构决策）。"""
    n = len(times_ms)
    if n < 2:
        return "缓存建议：样本不足，请在 RUN_OCR_REPEAT 中增加重复次数后再评估。"
    rel = stdev / mean if mean > 0 else 0.0
    parts = []
    if mean >= 800:
        parts.append("平均耗时偏高（≥800ms），若同一 widget 会被多次读取，优先考虑短 TTL 缓存（建议键：hwnd + widget_id + lang + 可选图像 hash）。")
    elif mean >= 300:
        parts.append("平均耗时中等；可在热点路径上按需加缓存。")
    else:
        parts.append("平均耗时较低，默认不必为 OCR 单独加缓存层。")
    if n >= 3 and rel < 0.12:
        parts.append("多次测量方差相对均值较小，缓存命中时延可预期。")
    elif rel >= 0.25:
        parts.append("方差较大（可能受系统负载或 Tesseract 波动影响），缓存仍可减少尾延迟，但需实测 TTL。")
    return "缓存建议：" + " ".join(parts)
