"""
Desktop DOM 读取验证脚本（调用服务端 /ui/dom/read）

用途
    对已运行的 API 服务发起 ``POST /ui/dom/read``，检查返回 JSON 的结构、深度与可选校验；
    支持交互选窗口或按标题/活动窗口读取。

与 pytest 的关系
    **不属于** ``pytest`` 默认收集的用例（文件名虽以 test_ 开头，但放在仓库根目录，
    意图为**手动/半自动**工具）。运行前请启动 ``server.py``，再执行：

    ``python test_ui_dom_reader.py --help``

支持：
- 列出窗口并交互选择，或指定活动窗口 / 标题
- 可配置解析深度与其它 UIReadOptions
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Set

import requests


DEFAULT_API_BASE = "http://127.0.0.1:8765"
DEFAULT_API_KEY = "desktop-control-key"
MAX_DEPTH_LIMIT = (1, 30)
MAX_PRINT_ELEMENTS = 30


def flatten_elements(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    stack = [root] if root else []
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(node.get("children", [])))
    return out


def no_cycles_in_tree(root: Dict[str, Any]) -> bool:
    visited: Set[str] = set()
    stack = [root] if root else []
    while stack:
        node = stack.pop()
        node_id = node.get("id", "")
        if node_id in visited:
            return False
        visited.add(node_id)
        stack.extend(node.get("children", []))
    return True


def bounds_are_screen_coordinates(elements: List[Dict[str, Any]]) -> bool:
    for item in elements:
        bounds = item.get("bounds", {})
        if not isinstance(bounds.get("x"), int) or not isinstance(bounds.get("y"), int):
            return False
        if not isinstance(bounds.get("width"), int) or not isinstance(bounds.get("height"), int):
            return False
    return True


def api_headers(api_key: str) -> Dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def fetch_windows(base: str, api_key: str, timeout: float) -> List[Dict[str, Any]]:
    resp = requests.get(f"{base.rstrip('/')}/windows", headers=api_headers(api_key), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"获取窗口列表失败：{data}")
    return list(data.get("windows") or [])


def print_window_list(windows: List[Dict[str, Any]], max_rows: Optional[int] = None) -> None:
    rows = windows if max_rows is None else windows[:max_rows]
    for i, w in enumerate(rows):
        title = (w.get("title") or "").strip() or "<空标题>"
        w_px = w.get("width", "?")
        h_px = w.get("height", "?")
        mini = "最小化" if w.get("isMinimized") else ""
        print(f"  [{i + 1}] {title}  ({w_px}x{h_px}) {mini}".rstrip())
    if max_rows is not None and len(windows) > max_rows:
        print(f"  ... 共 {len(windows)} 个窗口，仅显示前 {max_rows} 个")


def prompt_int(message: str, default: int, min_v: int, max_v: int) -> int:
    raw = input(f"{message} [{default}]: ").strip()
    if not raw:
        return default
    try:
        v = int(raw, 10)
    except ValueError:
        print(f"无效数字，使用默认值 {default}", file=sys.stderr)
        return default
    if v < min_v or v > max_v:
        print(f"需在 {min_v}-{max_v} 之间，使用默认值 {default}", file=sys.stderr)
        return default
    return v


def interactive_pick_window(windows: List[Dict[str, Any]]) -> Optional[str]:
    """返回 window_title；None 表示活动窗口。"""
    print("\n可选窗口（输入序号选择；0 = 当前活动窗口，不按标题匹配）：")
    print_window_list(windows, max_rows=40)
    raw = input("序号 [0]: ").strip()
    if not raw:
        return None
    try:
        idx = int(raw, 10)
    except ValueError:
        print("无效序号，使用活动窗口", file=sys.stderr)
        return None
    if idx == 0:
        return None
    if idx < 1 or idx > len(windows):
        print("序号超出范围，使用活动窗口", file=sys.stderr)
        return None
    title = windows[idx - 1].get("title") or ""
    if not title.strip():
        print("所选窗口无标题，改用活动窗口", file=sys.stderr)
        return None
    return title


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="测试 /ui/dom/read：可选窗口与解析深度")
    p.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API 根地址（默认 {DEFAULT_API_BASE}）")
    p.add_argument("--api-key", default=DEFAULT_API_KEY, help="X-API-Key")
    p.add_argument("--timeout", type=float, default=30.0, help="HTTP 超时秒数")
    p.add_argument(
        "-w",
        "--window-title",
        default=None,
        help="目标窗口标题（与 pygetwindow 一致，支持部分匹配）；不传则进入交互或 --active",
    )
    p.add_argument(
        "--active",
        action="store_true",
        help="读取当前活动窗口（不传 window_title）",
    )
    p.add_argument(
        "-d",
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help=f"UI 树最大深度 {MAX_DEPTH_LIMIT[0]}-{MAX_DEPTH_LIMIT[1]}（默认交互或 8）",
    )
    p.add_argument("--include-offscreen", action="store_true", help="包含屏幕外元素")
    p.add_argument("--include-invisible", action="store_true", help="包含不可见元素")
    p.add_argument("--no-include-disabled", action="store_true", help="排除不可用元素（默认包含）")
    p.add_argument(
        "--no-semantic",
        action="store_true",
        help="不生成 Semantic DOM（仅 Raw）",
    )
    p.add_argument(
        "--semantic-text-labels",
        action="store_true",
        help="Semantic 中额外包含可见文本节点",
    )
    p.add_argument("--max-print", type=int, default=MAX_PRINT_ELEMENTS, help="最多打印多少条元素详情")
    p.add_argument("--json-out", type=str, default=None, help="将完整 JSON 响应写入文件")
    p.add_argument("--list-only", action="store_true", help="仅列出窗口后退出")
    p.add_argument("--skip-validation", action="store_true", help="跳过结构断言（仅调试用）")
    return p


def main() -> None:
    args = build_parser().parse_args()
    base = args.api_base.rstrip("/")
    headers = api_headers(args.api_key)

    try:
        windows = fetch_windows(base, args.api_key, args.timeout)
    except requests.RequestException as e:
        print(f"请求失败：{e}", file=sys.stderr)
        sys.exit(1)

    if args.list_only:
        print(f"共 {len(windows)} 个窗口：")
        print_window_list(windows)
        return

    window_title: Optional[str]
    if args.active:
        window_title = None
    elif args.window_title is not None:
        window_title = args.window_title.strip() or None
    else:
        window_title = interactive_pick_window(windows)

    if args.max_depth is None:
        max_depth = prompt_int("max_depth", 8, MAX_DEPTH_LIMIT[0], MAX_DEPTH_LIMIT[1])
    else:
        max_depth = args.max_depth
        if max_depth < MAX_DEPTH_LIMIT[0] or max_depth > MAX_DEPTH_LIMIT[1]:
            print(f"max_depth 必须在 {MAX_DEPTH_LIMIT[0]}-{MAX_DEPTH_LIMIT[1]} 之间", file=sys.stderr)
            sys.exit(2)

    body: Dict[str, Any] = {
        "max_depth": max_depth,
        "include_offscreen": args.include_offscreen,
        "include_disabled": not args.no_include_disabled,
        "include_invisible": args.include_invisible,
        "include_semantic": not args.no_semantic,
        "semantic_include_text_labels": args.semantic_text_labels,
    }
    if window_title is not None:
        body["window_title"] = window_title

    print("\n请求参数:", json.dumps(body, ensure_ascii=False))
    label = window_title if window_title else "<活动窗口>"
    print(f"目标: {label} | max_depth={max_depth}\n")

    try:
        resp = requests.post(
            f"{base}/ui/dom/read",
            headers=headers,
            json=body,
            timeout=args.timeout,
        )
    except requests.RequestException as e:
        print(f"DOM 读取失败：{e}", file=sys.stderr)
        sys.exit(1)

    print("HTTP:", resp.status_code)
    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(resp.text[:500])
        sys.exit(1)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已写入: {args.json_out}")

    if resp.status_code not in (200, 206):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        sys.exit(1)

    if data.get("schema_version") != "desktop_dom.v1":
        print(f"schema_version 不匹配：{data.get('schema_version')!r}", file=sys.stderr)
        sys.exit(2)
    root = data.get("dom", {}).get("root")
    elements = flatten_elements(root) if root else []

    if not args.skip_validation:
        errors: List[str] = []
        if not all((item.get("id") or "").strip() for item in elements):
            errors.append("存在空元素ID")
        if root and not no_cycles_in_tree(root):
            errors.append("树结构存在环")
        if not bounds_are_screen_coordinates(elements):
            errors.append("bounds 不是统一屏幕坐标结构")
        if errors:
            for e in errors:
                print(f"验证失败: {e}", file=sys.stderr)
            sys.exit(3)

    print("window:", data.get("window", {}).get("title"))
    print("element_count:", data.get("quality", {}).get("element_count"))
    print("score:", data.get("quality", {}).get("score"))
    print("truncated:", data.get("stats", {}).get("truncated"))
    if data.get("stats", {}).get("truncated_reason"):
        print("truncated_reason:", data.get("stats", {}).get("truncated_reason"))
    print("validation:", "skipped" if args.skip_validation else "OK")

    sem = data.get("semantic")
    if sem:
        st = sem.get("stats") or {}
        print("\n--- Semantic DOM ---")
        print("all_elements:", st.get("all_elements"))
        print("actionable_elements:", st.get("actionable_elements"))
        print("semantic_elements:", len(sem.get("elements") or []))

    max_print = max(0, args.max_print)
    print("\n--- Elements (detailed) ---")
    for idx, item in enumerate(elements[:max_print], start=1):
        bounds = item.get("bounds", {})
        print(
            f"[{idx}] id={item.get('id', '')} | "
            f"type={item.get('type', '')} | "
            f"text={repr(item.get('text', ''))} | "
            f"source={item.get('source', '')} | "
            f"status={item.get('status', '')} | "
            f"bounds=({bounds.get('x')}, {bounds.get('y')}, {bounds.get('width')}, {bounds.get('height')})"
        )

    if len(elements) > max_print:
        print(f"... and {len(elements) - max_print} more elements")


if __name__ == "__main__":
    main()
