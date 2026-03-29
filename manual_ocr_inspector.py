#!/usr/bin/env python3
"""
交互式 OCR / UIA 对比检查器（人类验收，非 pytest）。

流程：列出窗口 → 选择 → 列出控件 → **循环**：输入列表下标单次 OCR、或 `a` / `aN` 从该下标起对本列表依次调用 `/vision/ocr/widget`（每批最多 `--max-batch` 个，单个失败则跳过继续）、或 `q` 退出；可选在裁剪图上画红框与绿框（OCR bbox）。落盘路径与命名规则不变。

前置：本机已启动 API（默认 http://127.0.0.1:8765），已安装 Tesseract。

用法::

    python manual_ocr_inspector.py
    python manual_ocr_inspector.py --lang chi_sim+eng --max-batch 12

环境变量（与 test_client 一致；推荐写入项目根 ``.env``，启动时自动加载）::

    DESKTOP_API_BASE / DESKTOP_API_KEY / DESKTOP_HTTP_TIMEOUT_S / DESKTOP_OCR_LANG
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import env_bootstrap  # noqa: F401
import requests

from settings import (
    default_ui_max_depth,
    tooling_api_base,
    tooling_api_key,
    tooling_http_timeout_s,
    tooling_ocr_lang,
)

DEFAULT_BASE = tooling_api_base()
DEFAULT_KEY = tooling_api_key()
TIMEOUT = tooling_http_timeout_s(120.0)


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


def _headers(api_key: str) -> Dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _redact_key(k: str) -> str:
    k = k or ""
    if len(k) <= 8:
        return "(短密钥已隐藏)"
    return f"{k[:4]}…{k[-3:]} (len={len(k)})"


def _print_banner(base: str, key: str, lang: str, psm: str, crop_padding: int) -> None:
    print("=" * 60)
    print(" manual_ocr_inspector — UIA vs OCR 对比")
    print("=" * 60)
    print(f"  API_BASE   : {base}")
    print(f"  API_KEY    : {_redact_key(key)}")
    print(f"  lang       : {lang}")
    print(f"  tesseract  : {psm}")
    print(f"  crop_pad   : {crop_padding}px")
    print("=" * 60 + "\n")


def _ok_envelope(j: Dict[str, Any]) -> Dict[str, Any]:
    if not j.get("success"):
        err = j.get("error") or {}
        raise SystemExit(f"API 错误: {err.get('code')} — {err.get('message')}")
    return j.get("data") or {}


def _choose_index(prompt: str, n: int) -> Optional[int]:
    raw = input(prompt).strip()
    if raw.casefold() in {"q", "quit", "exit"}:
        return None
    try:
        i = int(raw)
    except ValueError:
        print("请输入整数序号或 q 退出。")
        return _choose_index(prompt, n)
    if i < 0 or i >= n:
        print(f"序号须在 [0, {n - 1}] 内。")
        return _choose_index(prompt, n)
    return i


def _save_overlay(image_path: str, ocr_lines: List[Any], out_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:
        print(f"跳过叠加图（未安装 Pillow）: {e}")
        return
    p = Path(image_path)
    if not p.is_file():
        print(f"跳过叠加图（文件不存在）: {image_path}")
        return
    im = Image.open(p).convert("RGB")
    dr = ImageDraw.Draw(im)
    w, h = im.size
    dr.rectangle([0, 0, w - 1, h - 1], outline="red", width=2)
    for line in ocr_lines or []:
        if not isinstance(line, dict):
            continue
        bb = line.get("bbox")
        if not isinstance(bb, list) or len(bb) != 4:
            continue
        x, y, bw, bh = (int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3]))
        dr.rectangle([x, y, x + bw, y + bh], outline="lime", width=1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)
    print(f"已写入叠加图: {out_path}")


def _print_compare(role: Any, uia: str, ocr_t: str, wid: str, *, lines_n: Optional[int] = None) -> None:
    print("-" * 50)
    print(f"  id       : {wid}")
    print(f"  role     : {role}")
    print(f"  UIA text : {uia!r}")
    print(f"  OCR text : {ocr_t!r}")
    if lines_n is not None:
        print(f"  lines    : {lines_n}")


BATCH_CMD_RE = re.compile(r"^a(\d*)$", re.IGNORECASE)


def _read_widget_once(
    sess: requests.Session,
    base: str,
    h: Dict[str, str],
    hwnd: int,
    wid: str,
    *,
    lang: str,
    psm: str,
    crop_padding: int,
    max_depth: int,
    timeout: float,
) -> tuple[bool, Dict[str, Any]]:
    """调用 /vision/ocr/widget，返回 (成功, JSON 根对象)。"""
    orr = sess.post(
        f"{base}/vision/ocr/widget",
        headers=h,
        json={
            "id": wid,
            "target_hwnd": hwnd,
            "max_depth": max_depth,
            "lang": lang,
            "tesseract_config": psm,
            "crop_padding_px": crop_padding,
        },
        timeout=timeout,
    )
    try:
        oj = orr.json()
    except Exception as e:
        return False, {"_parse_error": str(e), "text": orr.text[:500]}
    if orr.status_code != 200 or not oj.get("success"):
        return False, oj
    return True, oj


def _print_ocr_result(
    od: Dict[str, Any],
    wid: str,
    *,
    list_index: Optional[int] = None,
    no_overlay: bool,
    overlay_dir: Path,
    safe_lang: str,
) -> None:
    wg = od.get("widget") or {}
    oc = od.get("ocr") or {}
    ols = list(oc.get("lines") or [])
    if list_index is not None:
        print(f"\n  ----- 列表下标 [{list_index}] -----")
    _print_compare(
        wg.get("role"),
        str(wg.get("text") or ""),
        str(oc.get("text") or ""),
        wid,
        lines_n=len(ols),
    )
    print(f"  image_path : {od.get('image_path')}")
    print(f"  image_size : {od.get('image_width')} x {od.get('image_height')}")
    if od.get("capture_bounds"):
        print(f"  capture_bounds : {od.get('capture_bounds')}")

    if not no_overlay and od.get("image_path"):
        suf = f"_{list_index}" if list_index is not None else ""
        op = overlay_dir / f"ocr_inspector_overlay_{safe_lang}_{wid[:16]}{suf}.png"
        _save_overlay(str(od["image_path"]), ols, op)


def main() -> int:
    p = argparse.ArgumentParser(description="交互式 OCR / UIA 检查器")
    p.add_argument("--base-url", default=DEFAULT_BASE, help="API 根 URL")
    p.add_argument("--api-key", default=DEFAULT_KEY, help="X-API-Key")
    p.add_argument("--lang", default=tooling_ocr_lang())
    p.add_argument("--psm", default="--psm 6", help="传给 tesseract_config")
    p.add_argument("--max-batch", type=int, default=15, help="a / aN 每批最多连续 read_widget 次数")
    p.add_argument(
        "--no-focus",
        action="store_true",
        help="不调用 /windows/focus（与默认 best_effort 聚焦二选一省略）",
    )
    p.add_argument("--no-overlay", action="store_true", help="不写叠加 PNG")
    p.add_argument(
        "--crop-padding",
        type=int,
        default=4,
        metavar="PX",
        help="传给 API 的 crop_padding_px（UIA 裁剪四周各扩展像素，利于 OCR 不切边；0 关闭）",
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    h = _headers(args.api_key)

    _print_banner(base, args.api_key, args.lang, args.psm, args.crop_padding)

    sess = _session()
    try:
        r = sess.get(f"{base}/health", timeout=5)
        if r.status_code != 200:
            print(f"无法连接服务: GET /health -> {r.status_code}")
            return 1
    except Exception as e:
        print(f"无法连接服务 {base}: {e}")
        return 1

    # Step 1: windows
    wr = sess.get(f"{base}/windows", headers=h, timeout=TIMEOUT)
    if wr.status_code != 200:
        print(f"GET /windows 失败: {wr.status_code} {wr.text[:300]}")
        return 1
    wj = wr.json()
    try:
        data = _ok_envelope(wj)
    except SystemExit as e:
        print(e)
        return 1
    windows: List[Dict[str, Any]] = data.get("windows") or []
    if not windows:
        print("没有可用窗口。请打开记事本/计算器等后重试。")
        return 1

    for i, w in enumerate(windows):
        t = str(w.get("title") or "")
        hwnd = w.get("hwnd")
        print(f"  [{i}] (hwnd={hwnd}) {t[:100]}")

    idx = _choose_index("选择窗口序号: ", len(windows))
    if idx is None:
        return 0
    win = windows[idx]
    hwnd = int(win.get("hwnd") or 0)
    if hwnd <= 0:
        print("无效 hwnd")
        return 1

    if not args.no_focus:
        # best_effort：服务进程常被系统禁止抢前台，置前失败仍返回 200，后续可用 window_hwnd 查 UIA/OCR
        fr = sess.post(
            f"{base}/windows/focus",
            headers=h,
            json={"hwnd": hwnd, "best_effort": True},
            timeout=TIMEOUT,
        )
        fj = fr.json()
        if fr.status_code == 200 and fj.get("success"):
            fd = fj.get("data") or {}
            if fd.get("focused") is False:
                print(
                    "未能置前（Windows 常限制后台服务抢前台；不影响按 hwnd 的 UIA 与 PrintWindow 裁剪）。\n"
                )
            else:
                print("已聚焦该窗口。\n")
        else:
            print(f"聚焦请求异常: {fr.status_code} {fj}\n")
        time.sleep(0.25)

    # Step 2: widgets
    qr = sess.post(
        f"{base}/widgets/query",
        headers=h,
        json={
            "window_hwnd": hwnd,
            "max_depth": default_ui_max_depth(),
            "filters": {},
            "limit": 200,
            "select": ["id", "role", "text", "normalized", "bounds"],
        },
        timeout=TIMEOUT,
    )
    qj = qr.json()
    if qr.status_code not in (200, 206) or not qj.get("success"):
        print(f"widgets/query 失败: {qr.status_code} {qj}")
        return 1
    qdata = qj.get("data") or {}
    widgets: List[Dict[str, Any]] = qdata.get("widgets") or []
    if not widgets:
        print("该窗口无 widgets 返回。")
        return 1

    for i, w in enumerate(widgets):
        b = w.get("bounds") or {}
        role = w.get("role")
        wid = str(w.get("id") or "")[:24]
        raw_t = w.get("text")
        if isinstance(raw_t, dict):
            tx = (raw_t.get("value") or w.get("text_legacy") or "")[:40]
        else:
            tx = (raw_t or w.get("text_legacy") or w.get("normalized") or "")[:40]
        print(f"  [{i}] id={wid!r}  {role}  text={tx!r}  bounds={b}")

    overlay_dir = Path("updates") / "screenshots" / time.strftime("%Y-%m-%d", time.gmtime())
    safe_lang = re.sub(r"[^a-z0-9_+-]+", "_", args.lang, flags=re.I)[:24]

    while True:
        print(
            "\n输入列表下标单次 OCR；a 或 aN 从该下标起依次 /vision/ocr/widget（每批最多 "
            f"{args.max_batch} 个，失败跳过）；q 退出。"
        )
        print("  例: a → 从 0 开始；a16 → 从 16 开始；a50 → 从 50 读到列表末尾（不足一批也读完）。")
        choice_raw = input("> ").strip()
        choice = choice_raw.casefold()
        if choice in {"q", "quit", "exit"}:
            break

        batch_m = BATCH_CMD_RE.match(choice_raw.strip())
        if batch_m is not None:
            suffix = batch_m.group(1) or ""
            try:
                start = int(suffix) if suffix else 0
            except ValueError:
                print("无效：a 后可跟非负整数起始下标，如 a16。")
                continue
            if start < 0 or start >= len(widgets):
                print(f"起始下标须在 [0, {len(widgets) - 1}] 内。")
                continue
            end = min(start + args.max_batch, len(widgets))
            n_batch = end - start
            print(
                f"\n批量 OCR：列表下标 [{start}, {end}) 共 {n_batch} 个控件（每控件一次 read_widget）。\n"
            )
            for wi in range(start, end):
                w = widgets[wi]
                wid = str(w.get("id") or "")
                if not wid:
                    print(f"  [{wi}] 跳过：无 widget id")
                    continue
                ok, oj = _read_widget_once(
                    sess,
                    base,
                    h,
                    hwnd,
                    wid,
                    lang=args.lang,
                    psm=args.psm,
                    crop_padding=args.crop_padding,
                    max_depth=default_ui_max_depth(),
                    timeout=TIMEOUT,
                )
                if not ok:
                    err = (oj.get("error") or {}) if isinstance(oj, dict) else {}
                    msg = err.get("message") if isinstance(err, dict) else None
                    if msg:
                        print(f"  [{wi}] 不可读: {msg}")
                    else:
                        print(f"  [{wi}] 不可读: {oj}")
                    continue
                od = oj.get("data") or {}
                _print_ocr_result(
                    od,
                    wid,
                    list_index=wi,
                    no_overlay=args.no_overlay,
                    overlay_dir=overlay_dir,
                    safe_lang=safe_lang,
                )
            print(f"\n本批结束（已处理下标 {start}..{end - 1}）。")
            continue

        try:
            wi = int(choice)
        except ValueError:
            print("无效输入：整数下标、a / aN 或 q。")
            continue
        if wi < 0 or wi >= len(widgets):
            print("序号越界。")
            continue
        w = widgets[wi]
        wid = str(w.get("id") or "")
        if not wid:
            print("无 widget id")
            continue

        ok, oj = _read_widget_once(
            sess,
            base,
            h,
            hwnd,
            wid,
            lang=args.lang,
            psm=args.psm,
            crop_padding=args.crop_padding,
            max_depth=default_ui_max_depth(),
            timeout=TIMEOUT,
        )
        if not ok:
            print(f"read_widget 失败: {oj}")
            continue
        od = oj.get("data") or {}
        _print_ocr_result(
            od,
            wid,
            list_index=None,
            no_overlay=args.no_overlay,
            overlay_dir=overlay_dir,
            safe_lang=safe_lang,
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已中断。")
        raise SystemExit(130)
