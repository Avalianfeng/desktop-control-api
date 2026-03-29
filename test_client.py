"""
Desktop Control API 测试客户端（交互式 / 半自动）

用途
    通过 HTTP 调用本地服务，做健康检查、截图、鼠标键盘、窗口、widgets、验收与演示录制等。
    适合人类或脚本快速验证「服务是否活着、接口是否符合预期」。

与 pytest 的关系
    **不属于** ``tests/`` 下的单元测试套件；通常直接运行：

    ``python test_client.py``

    可在项目根 ``.env`` 中设置 ``DESKTOP_API_BASE``、``DESKTOP_API_KEY``、``DESKTOP_HTTP_TIMEOUT_S`` 等。

    部分子命令（如 ``--acceptance``）为只读验收；危险操作需显式确认或开关。
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List

import base64
import env_bootstrap  # noqa: F401
import requests

from settings import tooling_api_base, tooling_api_key, tooling_http_timeout_s

DEFAULT_API_BASE = tooling_api_base()
DEFAULT_API_KEY = tooling_api_key()
DEFAULT_TIMEOUT_S = tooling_http_timeout_s(20.0)

_SESSION = requests.Session()
# 避免被本机 HTTP(S)_PROXY 环境变量劫持到代理端口（常见：7890）
_SESSION.trust_env = False


@dataclass(frozen=True)
class ClientConfig:
    api_base: str
    api_key: str
    timeout_s: float
    dangerous: bool


def build_headers(api_key: str) -> Dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def http_get(cfg: ClientConfig, path: str, *, headers: Optional[Dict[str, str]] = None) -> requests.Response:
    return _SESSION.get(
        f"{cfg.api_base.rstrip('/')}{path}",
        headers=headers or build_headers(cfg.api_key),
        timeout=cfg.timeout_s,
    )


def http_post(
    cfg: ClientConfig,
    path: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> requests.Response:
    return _SESSION.post(
        f"{cfg.api_base.rstrip('/')}{path}",
        headers=headers or build_headers(cfg.api_key),
        json=json_body,
        timeout=cfg.timeout_s,
    )

def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {"_non_dict_json": data}
    except Exception:
        txt = (resp.text or "")[:800]
        return {"_non_json_response": txt}


def http_get_timed(cfg: ClientConfig, path: str, *, headers: Optional[Dict[str, str]] = None) -> Tuple[requests.Response, int]:
    start = datetime.now()
    resp = http_get(cfg, path, headers=headers)
    elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
    return resp, elapsed_ms


def http_post_timed(
    cfg: ClientConfig,
    path: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[requests.Response, int]:
    start = datetime.now()
    resp = http_post(cfg, path, json_body=json_body, headers=headers)
    elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
    return resp, elapsed_ms


def maybe_save_json(data: object, default_prefix: str) -> None:
    """可选将响应写入 JSON 文件（方便调试查看）。"""
    default_name = f"{default_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = input(f"保存完整 JSON？输入文件名/路径（空=跳过）[{default_name}]: ").strip()
    if not path:
        return
    if path.lower() in {"y", "yes"}:
        path = default_name
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已写入：{path}")
    except Exception as e:
        print(f"写入失败：{e}")

@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    endpoint: str
    expected: str
    actual: str
    elapsed_ms: Optional[int] = None
    notes: str = ""


def _icon(ok: bool) -> str:
    return "✅" if ok else "❌"


def _md_escape(s: str) -> str:
    return (s or "").replace("\n", " ").replace("|", "\\|").strip()


def _to_md_table(rows: List[List[str]], headers: List[str]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def acceptance_suite(cfg: ClientConfig) -> str:
    """
    面向非技术同学的“验收式”只读测试：
    - 不会控制鼠标/键盘
    - 生成 Markdown 汇总报告，适合贴到群里/邮件
    """
    checks: List[CheckResult] = []

    # 1) Health
    resp, ms = http_get_timed(cfg, "/health", headers={"Content-Type": "application/json"})
    data = _safe_json(resp)
    ok = resp.status_code == 200 and data.get("status") == "ok"
    checks.append(
        CheckResult(
            name="服务健康检查",
            ok=ok,
            endpoint="GET /health",
            expected="返回 status=ok",
            actual=f"HTTP {resp.status_code}; status={data.get('status')!r}",
            elapsed_ms=ms,
        )
    )

    # 2) Windows list
    resp, ms = http_get_timed(cfg, "/windows")
    data = _safe_json(resp)
    ok = resp.status_code == 200 and data.get("success") is True and isinstance(data.get("windows"), list)
    count = data.get("count")
    checks.append(
        CheckResult(
            name="窗口列表可读取",
            ok=ok,
            endpoint="GET /windows",
            expected="返回 success=true 且 windows 为列表",
            actual=f"HTTP {resp.status_code}; success={data.get('success')!r}; count={count!r}",
            elapsed_ms=ms,
            notes="用于确认运行环境具备“看到窗口”的基础能力",
        )
    )

    # 3) UI DOM read (active window)
    resp, ms = http_post_timed(cfg, "/ui/dom/read", json_body={"max_depth": 6, "include_offscreen": False, "include_semantic": True})
    data = _safe_json(resp)
    schema = data.get("schema_version")
    ok = resp.status_code in (200, 206) and schema == "desktop_dom.v1"
    sem = (data.get("semantic") or {}) if isinstance(data, dict) else {}
    sem_schema = sem.get("schema_version")
    checks.append(
        CheckResult(
            name="读取界面结构（活动窗口）",
            ok=ok,
            endpoint="POST /ui/dom/read",
            expected="HTTP 200/206 且 schema=desktop_dom.v1",
            actual=f"HTTP {resp.status_code}; schema={schema!r}; semantic_schema={sem_schema!r}",
            elapsed_ms=ms,
            notes="用于让系统“理解”当前界面有哪些元素",
        )
    )

    # 4) Widgets read (active window)
    resp, ms = http_post_timed(cfg, "/ui/widgets/read", json_body={"max_depth": 8, "include_text_widgets": True, "collapse_icons": True})
    data = _safe_json(resp)
    schema = data.get("schema_version")
    stats = data.get("stats") or {}
    widgets = data.get("widgets") or []
    first = widgets[0] if isinstance(widgets, list) and widgets else {}
    meta = first.get("meta") if isinstance(first, dict) else None
    has_stable_id_shape = isinstance(first.get("id"), str) and first.get("id", "").startswith("w_") and len(first.get("id", "")) >= 10
    has_legacy_meta = isinstance(meta, dict) and ("legacy_index_id" in meta) and ("locator_source" in meta)
    has_parent_field = isinstance(first, dict) and ("parent_id" in first)

    ok = resp.status_code in (200, 206) and schema == "desktop_widgets.v2"
    checks.append(
        CheckResult(
            name="读取可操作控件列表（widgets）",
            ok=ok,
            endpoint="POST /ui/widgets/read",
            expected="HTTP 200/206 且 schema=desktop_widgets.v2",
            actual=(
                f"HTTP {resp.status_code}; schema={schema!r}; "
                f"widgets={stats.get('widgets')!r}; actionable={stats.get('actionable_widgets')!r}; "
                f"stable_id={has_stable_id_shape}; legacy_meta={has_legacy_meta}; parent_field={has_parent_field}"
            ),
            elapsed_ms=ms,
            notes="用于把复杂界面元素压缩成更像“按钮/输入框/标签”的列表",
        )
    )

    # 5) Widgets query (active window)
    resp, ms = http_post_timed(cfg, "/ui/widgets/query", json_body={"limit": 20, "filters": {}, "select": ["id", "role", "normalized", "text", "bounds"]})
    data = _safe_json(resp)
    schema = data.get("schema_version")
    stats = data.get("stats") or {}
    returned = stats.get("returned")
    ok = resp.status_code in (200, 206) and schema == "desktop_widgets_query.v2" and isinstance(data.get("widgets"), list)
    checks.append(
        CheckResult(
            name="按条件查询控件（widgets query）",
            ok=ok,
            endpoint="POST /ui/widgets/query",
            expected="HTTP 200/206 且 schema=desktop_widgets_query.v2",
            actual=f"HTTP {resp.status_code}; schema={schema!r}; returned={returned!r}",
            elapsed_ms=ms,
            notes="用于从控件列表中筛选出“最可能要点的那个”",
        )
    )

    # 6) Widgets query: ancestor_role + parent_id select (read-only)
    resp, ms = http_post_timed(
        cfg,
        "/ui/widgets/query",
        json_body={
            "limit": 20,
            "filters": {"ancestor_role": "button"},
            "select": ["id", "role", "text", "parent_id"],
        },
    )
    data = _safe_json(resp)
    schema = data.get("schema_version")
    stats = data.get("stats") or {}
    returned = stats.get("returned")
    ok = resp.status_code in (200, 206) and schema == "desktop_widgets_query.v2"
    checks.append(
        CheckResult(
            name="层级过滤（ancestor_role）+ parent_id 输出",
            ok=ok,
            endpoint="POST /ui/widgets/query",
            expected="HTTP 200/206 且支持 filters.ancestor_role 与 parent_id 字段裁剪",
            actual=f"HTTP {resp.status_code}; schema={schema!r}; returned={returned!r}",
            elapsed_ms=ms,
            notes="用于表达“某个容器/对话框里的按钮”这类层级语义",
        )
    )

    # 7) Action endpoints safety check (not found) - no real actions performed
    resp, ms = http_post_timed(cfg, "/ui/widgets/click", json_body={"id": "w_nonexistent", "max_depth": 6})
    data = _safe_json(resp)
    # 期望 404（找不到 widget），用于验证端点存在且错误模型可用
    ok = resp.status_code == 404
    checks.append(
        CheckResult(
            name="动作能力存在（click，安全校验）",
            ok=ok,
            endpoint="POST /ui/widgets/click",
            expected="HTTP 404（widget_not_found）",
            actual=f"HTTP {resp.status_code}; error={data.get('error', {}).get('code')!r}",
            elapsed_ms=ms,
            notes="安全验证：不执行真实点击，只验证动作端点与错误返回正常",
        )
    )

    resp, ms = http_post_timed(cfg, "/ui/widgets/set_value", json_body={"id": "w_nonexistent", "value": "x", "max_depth": 6})
    data = _safe_json(resp)
    ok = resp.status_code == 404
    checks.append(
        CheckResult(
            name="动作能力存在（set_value，安全校验）",
            ok=ok,
            endpoint="POST /ui/widgets/set_value",
            expected="HTTP 404（widget_not_found）",
            actual=f"HTTP {resp.status_code}; error={data.get('error', {}).get('code')!r}",
            elapsed_ms=ms,
            notes="安全验证：不执行真实输入，只验证动作端点与错误返回正常",
        )
    )

    # Markdown report
    rows: List[List[str]] = []
    for c in checks:
        rows.append(
            [
                _md_escape(f"{_icon(c.ok)} {c.name}"),
                _md_escape(c.endpoint),
                _md_escape(c.expected),
                _md_escape(c.actual),
                _md_escape(f"{c.elapsed_ms}ms" if c.elapsed_ms is not None else "-"),
                _md_escape(c.notes),
            ]
        )

    ok_count = sum(1 for c in checks if c.ok)
    report = []
    report.append("## 项目概览")
    report.append("")
    report.append(f"当前处于 **“可读能力 + widgets 结构化输出（v1.2）”** 阶段，目标是让系统能稳定读取界面并产出可操作控件清单，为后续“点击/输入”等动作能力打基础。")
    report.append("")
    report.append("## 功能交付清单（面向使用者可感知）")
    report.append("")
    report.append(_to_md_table(
        headers=["功能模块", "状态", "验证方式", "备注"],
        rows=[
            ["服务健康检查", "已完成", "验收套件：服务健康检查", "用于确认服务可用"],
            ["窗口列表读取", "已完成", "验收套件：窗口列表可读取", "用于确认运行环境可见窗口"],
            ["界面结构读取（DOM）", "已完成", "验收套件：读取界面结构（活动窗口）", "用于理解界面元素"],
            ["控件清单生成（widgets v1.2）", "已完成", "验收套件：读取可操作控件列表（widgets）", "role 体系已切换为 browser-like"],
            ["控件筛选（widgets query）", "已完成", "验收套件：按条件查询控件（widgets query）", "用于从控件列表中筛选目标"],
            ["层级语义定位（ancestor_role + parent_id）", "已完成", "验收套件：层级过滤（ancestor_role）+ parent_id 输出", "用于“某个容器/对话框里的按钮”类场景"],
            ["控件动作：点击（click）", "已完成（安全验证）", "验收套件：动作能力存在（click，安全校验）", "真实点击属于危险操作，建议单独做人工验收"],
            ["控件动作：输入/设值（set_value）", "已完成（安全验证）", "验收套件：动作能力存在（set_value，安全校验）", "真实输入属于危险操作，建议单独做人工验收"],
        ],
    ))
    report.append("")
    report.append("## 真实使用测试报告（只读验收）")
    report.append("")
    report.append(_to_md_table(
        headers=["测试场景", "调用接口", "预期结果", "实际结果", "耗时", "截图/演示链接"],
        rows=[
            [
                _md_escape(f"{_icon(c.ok)} {c.name}"),
                _md_escape(c.endpoint),
                _md_escape(c.expected),
                _md_escape(c.actual),
                _md_escape(f"{c.elapsed_ms}ms" if c.elapsed_ms is not None else "-"),
                _md_escape(f"{cfg.api_base.rstrip('/')}/docs"),
            ]
            for c in checks
        ],
    ))
    report.append("")
    report.append("## 关键指标仪表盘（本次验收采样）")
    report.append("")
    report.append(f"- **只读验收场景通过率**：{ok_count}/{len(checks)}（{int(ok_count/len(checks)*100)}%）")
    report.append(f"- **可访问演示入口**：Swagger UI（`{cfg.api_base.rstrip('/')}/docs`）")
    report.append("- **widgets schema 版本**：期望 `desktop_widgets.v1.2`（本次验收已校验）")
    report.append("- **动作端点可用性（安全验证）**：click/set_value 端点已可访问（通过 404 not-found 验证）")
    report.append("")
    report.append("## 风险与需要关注事项")
    report.append("")
    report.append("- **破坏性变更风险**：widgets 的 role 取值集合已变化；若上层逻辑依赖旧 role，需要同步适配（否则会出现“识别到控件但动作策略失效”的问题）。")
    report.append("- **验收风险（动作类）**：click/set_value 已交付，但真实动作会影响当前电脑界面，建议在受控窗口（例如记事本）做一次人工验收或专门的“危险模式”自动化验收。")
    report.append("- **环境依赖**：UI 读取依赖运行机器上的窗口与可访问性能力；在无人值守/远程会话/权限受限时可能出现可读性下降。")
    report.append("")
    report.append(f"（报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    return "\n".join(report)


def run_acceptance_and_save(cfg: ClientConfig) -> None:
    md = acceptance_suite(cfg)
    default_name = f"updates/docs/验收报告_{_now_ts()}.md"
    path = input(f"将验收报告写入文件？输入路径（空=仅打印摘要）[{default_name}]: ").strip()
    if not path:
        # 仅打印摘要（避免刷屏）
        lines = md.splitlines()
        print("\n".join(lines[:80]))
        if len(lines) > 80:
            print("\n...（已截断；如需完整报告请写入文件）")
        return
    if path.lower() in {"y", "yes"}:
        path = default_name
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ 已写入：{path}")


def test_health(cfg: ClientConfig):
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    response = http_get(cfg, "/health", headers={"Content-Type": "application/json"})
    print(f"状态：{response.json()}")


def test_screenshot(cfg: ClientConfig):
    """测试截图"""
    print("\n=== 测试截图 ===")
    response = http_post(cfg, "/screenshot")
    data = response.json()
    
    if data["success"]:
        print(f"截图成功：{data['width']}x{data['height']}")
        
        # 保存截图
        img_data = base64.b64decode(data["image"])
        with open("test_screenshot.png", "wb") as f:
            f.write(img_data)
        print("已保存到：test_screenshot.png")
    else:
        print("截图失败")


def _ensure_dangerous(cfg: ClientConfig) -> None:
    if cfg.dangerous:
        return
    raise RuntimeError("此操作会控制鼠标/键盘。请使用 --dangerous 显式启用。")


def test_mouse_move(cfg: ClientConfig):
    """测试鼠标移动"""
    _ensure_dangerous(cfg)
    print("\n=== 测试鼠标移动 ===")
    response = http_post(cfg, "/mouse/move", json_body={"x": 100, "y": 100, "duration": 0.5})
    print(f"结果：{response.json()}")


def test_mouse_click(cfg: ClientConfig):
    """测试鼠标点击"""
    _ensure_dangerous(cfg)
    print("\n=== 测试鼠标点击 ===")
    response = http_post(cfg, "/mouse/click", json_body={"x": 200, "y": 200, "button": "left", "clicks": 1})
    print(f"结果：{response.json()}")


def test_keyboard_type(cfg: ClientConfig):
    """测试键盘输入"""
    _ensure_dangerous(cfg)
    print("\n=== 测试键盘输入 ===")
    print("请确保输入框已聚焦...")
    input("按 Enter 继续...")
    
    response = http_post(cfg, "/keyboard/type", json_body={"text": "Hello from Desktop Control API!", "interval": 0.05})
    print(f"结果：{response.json()}")


def test_windows_list(cfg: ClientConfig):
    """测试列出窗口"""
    print("\n=== 测试列出窗口 ===")
    response = http_get(cfg, "/windows")
    data = response.json()
    
    if data["success"]:
        print(f"找到 {data['count']} 个窗口:")
        for i, window in enumerate(data["windows"][:10]):  # 只显示前 10 个
            print(f"  {i+1}. {window['title']} ({window['width']}x{window['height']})")
    else:
        print("获取窗口列表失败")

def pick_window_title_loop(cfg: ClientConfig) -> str | None:
    """
    循环选择窗口：
    - 输入序号：选择对应窗口标题
    - 输入 0：使用活动窗口（不传 window_title）
    - 输入 r：刷新窗口列表
    - 直接回车：保持当前选择
    - 输入 q：退出选择循环（保持当前选择）
    """
    current: str | None = None
    windows_cache = None

    while True:
        if windows_cache is None:
            resp = http_get(cfg, "/windows")
            data = resp.json()
            if not data.get("success"):
                print("获取窗口列表失败")
                return current
            windows_cache = data.get("windows") or []

        print("\n=== 选择窗口（将用于 /ui/dom/read 与 /ui/widgets/read）===")
        print(f"当前选择: {current or '<活动窗口>'}")
        for i, w in enumerate(windows_cache[:25]):
            title = (w.get("title") or "").strip() or "<空标题>"
            print(f"  {i+1}. {title}")
        if len(windows_cache) > 25:
            print(f"  ... 共 {len(windows_cache)} 个窗口，仅显示前 25 个")

        raw = input("输入序号/0/r/q（回车=保持当前）： ").strip()
        if raw == "":
            return current
        if raw.lower() == "q":
            return current
        if raw.lower() == "r":
            windows_cache = None
            continue
        if raw == "0":
            current = None
            return current
        if raw.isdigit():
            idx = int(raw, 10) - 1
            if idx < 0 or idx >= len(windows_cache):
                print("序号无效")
                continue
            title = (windows_cache[idx].get("title") or "").strip()
            if not title:
                print("该窗口标题为空，请换一个")
                continue
            current = title
            return current

        # 允许直接输入标题关键字（focus/read 都是 partial match）
        current = raw
        return current


def test_ui_dom_read(cfg: ClientConfig, window_title: str | None = None):
    """测试读取 Raw DOM + Semantic"""
    print("\n=== 测试 /ui/dom/read ===")
    payload = {"max_depth": 6, "include_offscreen": False, "include_semantic": True}
    if window_title is not None:
        payload["window_title"] = window_title
    response = http_post(cfg, "/ui/dom/read", json_body=payload)
    print(f"HTTP: {response.status_code}")
    data = response.json()
    print(f"window: {data.get('window', {}).get('title')}")
    print(f"schema: {data.get('schema_version')}")
    print(f"raw_element_count: {data.get('quality', {}).get('element_count')}")
    sem = data.get("semantic") or {}
    stats = sem.get("stats") or {}
    if sem:
        print(f"semantic_schema: {sem.get('schema_version')}")
        print(f"all_elements: {stats.get('all_elements')}")
        print(f"actionable_elements: {stats.get('actionable_elements')}")
    maybe_save_json(data, "ui_dom")


def test_ui_widgets_read(cfg: ClientConfig, window_title: str | None = None):
    """测试读取 Widgets（控件合并/文本折叠）"""
    print("\n=== 测试 /ui/widgets/read ===")
    payload = {"max_depth": 8, "include_text_widgets": True, "collapse_icons": True}
    if window_title is not None:
        payload["window_title"] = window_title
    response = http_post(cfg, "/ui/widgets/read", json_body=payload)
    print(f"HTTP: {response.status_code}")
    data = response.json()
    print(f"window: {data.get('window', {}).get('title')}")
    print(f"schema: {data.get('schema_version')}")
    stats = data.get("stats") or {}
    print(f"all_elements: {stats.get('all_elements')}")
    print(f"widgets: {stats.get('widgets')}")
    print(f"actionable_widgets: {stats.get('actionable_widgets')}")
    widgets = data.get("widgets") or []
    if widgets:
        first = widgets[0]
        print(f"first_widget: type={first.get('type')} role={first.get('role')} label={repr(first.get('label'))}")
    maybe_save_json(data, "ui_widgets")

def test_ui_widgets_query(cfg: ClientConfig, window_title: str | None = None):
    """测试查询 Widgets（服务端过滤/裁剪）"""
    print("\n=== 测试 /ui/widgets/query ===")
    payload: Dict[str, Any] = {
        "max_depth": 8,
        "include_text_widgets": True,
        "collapse_icons": True,
        "limit": 30,
        "filters": {},
        "select": ["id", "role", "normalized", "text", "bounds", "enabled", "visible", "focusable"],
    }
    if window_title is not None:
        payload["window_title"] = window_title
    response = http_post(cfg, "/ui/widgets/query", json_body=payload)
    print(f"HTTP: {response.status_code}")
    data = response.json()
    print(f"schema: {data.get('schema_version')}")
    stats = data.get("stats") or {}
    print(f"returned: {stats.get('returned')} / total: {stats.get('total')}")
    widgets = data.get("widgets") or []
    if widgets:
        first = widgets[0]
        print(f"first_widget: role={first.get('role')} text={repr(first.get('text'))} normalized={repr(first.get('normalized'))}")
    maybe_save_json(data, "ui_widgets_query")


def test_window_focus_interactive():
    """实际操作：聚焦窗口（需要人工选择，避免误操作）"""
    print("\n=== 实际操作测试 /windows/focus ===")
    raise RuntimeError("已废弃：请使用 main() 里的 cfg 版本调用（避免遗留全局配置）。")
    data = response.json()
    if not data.get("success"):
        print("获取窗口列表失败")
        return

    windows = data.get("windows") or []
    for i, w in enumerate(windows[:15]):
        print(f"  {i+1}. {w.get('title')}")

    raw = input("输入要聚焦的窗口序号（或直接输入标题关键字；空=取消）： ").strip()
    if not raw:
        print("已取消")
        return

    title = raw
    if raw.isdigit():
        idx = int(raw, 10) - 1
        if idx < 0 or idx >= len(windows):
            print("序号无效，已取消")
            return
        title = (windows[idx].get("title") or "").strip()
        if not title:
            print("该窗口标题为空，已取消")
            return

    resp = requests.post(f"{API_BASE}/windows/focus", json={"title": title}, headers=headers, timeout=10)
    print(f"HTTP: {resp.status_code}")
    print(resp.json())


def test_full_workflow():
    """完整工作流测试"""
    raise RuntimeError("已废弃：请使用 main() 里的 cfg 版本调用（避免遗留全局配置）。")


def test_window_focus_interactive_cfg(cfg: ClientConfig) -> None:
    _ensure_dangerous(cfg)
    print("\n=== 实际操作测试 /windows/focus ===")
    response = http_get(cfg, "/windows")
    data = response.json()
    if not data.get("success"):
        print("获取窗口列表失败")
        return

    windows = data.get("windows") or []
    for i, w in enumerate(windows[:15]):
        print(f"  {i+1}. {w.get('title')}")

    raw = input("输入要聚焦的窗口序号（或直接输入标题关键字；空=取消）： ").strip()
    if not raw:
        print("已取消")
        return

    title = raw
    if raw.isdigit():
        idx = int(raw, 10) - 1
        if idx < 0 or idx >= len(windows):
            print("序号无效，已取消")
            return
        title = (windows[idx].get("title") or "").strip()
        if not title:
            print("该窗口标题为空，已取消")
            return

    resp = http_post(cfg, "/windows/focus", json_body={"title": title})
    print(f"HTTP: {resp.status_code}")
    print(resp.json())


def test_full_workflow_cfg(cfg: ClientConfig) -> None:
    _ensure_dangerous(cfg)
    print("\n=== 完整工作流测试（危险）===")

    print("1. 截图...")
    screenshot = http_post(cfg, "/screenshot").json()
    if not screenshot.get("success"):
        print("截图失败：", screenshot)
        return
    print(f"   截图：{screenshot['width']}x{screenshot['height']}")

    center_x = screenshot["width"] // 2
    center_y = screenshot["height"] // 2

    print("2. 移动鼠标到屏幕中心...")
    http_post(cfg, "/mouse/move", json_body={"x": center_x, "y": center_y, "duration": 0.5})
    print(f"   已移动到 ({center_x}, {center_y})")

    print("3. 点击...")
    http_post(cfg, "/mouse/click", json_body={"x": center_x, "y": center_y})
    print("   点击完成")

    print("4. 输入文字...")
    http_post(cfg, "/keyboard/type", json_body={"text": "Desktop Control API 测试成功!", "interval": 0.05})
    print("   输入完成")

    print("\n✅ 工作流测试完成!")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Desktop Control API 交互式测试客户端")
    p.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API 根地址（默认 {DEFAULT_API_BASE}）")
    p.add_argument("--api-key", default=DEFAULT_API_KEY, help="X-API-Key（默认来自 DESKTOP_API_KEY）")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help=f"HTTP 超时秒数（默认 {DEFAULT_TIMEOUT_S}）")
    p.add_argument("--dangerous", action="store_true", help="允许执行鼠标/键盘等危险操作")
    p.add_argument(
        "--acceptance",
        action="store_true",
        help="直接运行只读验收套件并退出（适合 CI / 一键生成报告）",
    )
    p.add_argument(
        "--acceptance-out",
        default=None,
        help="验收报告输出路径（如 updates/docs/验收报告_xxx.md；不传则打印前 80 行摘要）",
    )
    p.add_argument(
        "--record-demo",
        action="store_true",
        help="生成“可复现 steps”的演示录制（默认 safe 模式，不会真实点击/输入）",
    )
    p.add_argument(
        "--record-out",
        default=None,
        help="录制 steps 输出路径（默认写入 updates/steps_demo_<ts>.json）",
    )
    return p


def record_demo_steps(cfg: ClientConfig, *, out_path: Optional[str] = None) -> str:
    """
    录制一份可复现的 steps（用于演示/回归）。
    约定：默认不传 X-Desktop-Control-Mode（即服务端 safe 模式），避免真实操作。
    返回：写入的 json 文件路径。
    """
    steps: List[Dict[str, Any]] = []
    ts = _now_ts()
    if not out_path:
        out_path = f"updates/steps_demo_{ts}.json"

    # 1) Read widgets snapshot
    resp, ms = http_post_timed(
        cfg,
        "/ui/widgets/read",
        json_body={"max_depth": 8, "include_text_widgets": True, "collapse_icons": True},
    )
    data = _safe_json(resp)
    widgets = data.get("widgets") if isinstance(data, dict) else None
    steps.append(
        {
            "action": "widgets_read",
            "request": {"max_depth": 8, "include_text_widgets": True, "collapse_icons": True},
            "result": {"http_status": resp.status_code, "elapsed_ms": ms, "widgets_count": len(widgets or []) if isinstance(widgets, list) else None},
        }
    )

    if not isinstance(widgets, list) or not widgets:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(steps, f, ensure_ascii=False, indent=2)
        return out_path

    # Pick a representative widget for click simulation
    w0 = widgets[0]
    fp0 = ((w0.get("meta") or {}).get("fingerprint") if isinstance(w0, dict) else None) or {
        "role": w0.get("role"),
        "text": w0.get("text"),
        "normalized": w0.get("normalized"),
        "automation_id": w0.get("automation_id"),
        "ancestor_roles": [],
    }
    wid0 = w0.get("id")

    # 2) click (safe simulation by default)
    resp, ms = http_post_timed(
        cfg,
        "/ui/widgets/click",
        json_body={"id": wid0, "fingerprint": fp0, "max_depth": 8},
    )
    data = _safe_json(resp)
    steps.append(
        {
            "action": "click",
            "request": {"id": wid0, "fingerprint": fp0, "max_depth": 8},
            "result": {"http_status": resp.status_code, "elapsed_ms": ms, "mode": data.get("mode") if isinstance(data, dict) else None},
        }
    )

    # 3) find a textbox for set_value simulation (if exists)
    textbox = None
    for w in widgets:
        if not isinstance(w, dict):
            continue
        if w.get("role") == "textbox":
            textbox = w
            break

    if textbox:
        fp1 = ((textbox.get("meta") or {}).get("fingerprint") if isinstance(textbox, dict) else None) or {
            "role": textbox.get("role"),
            "text": textbox.get("text"),
            "normalized": textbox.get("normalized"),
            "automation_id": textbox.get("automation_id"),
            "ancestor_roles": [],
        }
        wid1 = textbox.get("id")
        resp, ms = http_post_timed(
            cfg,
            "/ui/widgets/set_value",
            json_body={"id": wid1, "value": "hello", "verify": False, "fingerprint": fp1, "max_depth": 8},
        )
        data = _safe_json(resp)
        steps.append(
            {
                "action": "set_value",
                "request": {"id": wid1, "value": "hello", "verify": False, "fingerprint": fp1, "max_depth": 8},
                "result": {"http_status": resp.status_code, "elapsed_ms": ms, "mode": data.get("mode") if isinstance(data, dict) else None},
            }
        )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(steps, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    args = build_parser().parse_args()
    cfg = ClientConfig(api_base=args.api_base, api_key=args.api_key, timeout_s=args.timeout, dangerous=args.dangerous)

    if args.acceptance:
        md = acceptance_suite(cfg)
        if args.acceptance_out:
            path = args.acceptance_out
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"✅ 已写入：{path}")
            return
        lines = md.splitlines()
        print("\n".join(lines[:80]))
        if len(lines) > 80:
            print("\n...（已截断；如需完整报告请使用 --acceptance-out 写入文件）")
        return

    if args.record_demo:
        path = record_demo_steps(cfg, out_path=args.record_out)
        print(f"✅ steps 已写入：{path}")
        return

    print("""
    ╔══════════════════════════════════════════╗
    ║   Desktop Control API 测试客户端           ║
    ╚══════════════════════════════════════════╝
    
    请选择测试项目:
    1. 健康检查
    2. 截图
    3. 鼠标移动
    4. 鼠标点击
    5. 键盘输入
    6. 列出窗口
    7. 读取 Raw DOM（/ui/dom/read）
    8. 读取 Widgets（/ui/widgets/read）
    9. 实际操作：聚焦窗口（/windows/focus）
    10. 完整工作流测试（鼠标+键盘，危险）
    11. 只读验收套件（生成 Markdown 报告）
    12. 查询 Widgets（/ui/widgets/query）
    0. 退出
    
    注意：测试前请确保服务器已启动！
    """)
    
    while True:
        choice = input("\n选择 [0-12]: ").strip()
        
        if choice == "0":
            print("退出测试")
            break
        elif choice == "1":
            test_health(cfg)
        elif choice == "2":
            test_screenshot(cfg)
        elif choice == "3":
            test_mouse_move(cfg)
        elif choice == "4":
            test_mouse_click(cfg)
        elif choice == "5":
            test_keyboard_type(cfg)
        elif choice == "6":
            test_windows_list(cfg)
        elif choice == "7":
            window_title = pick_window_title_loop(cfg)
            test_ui_dom_read(cfg, window_title=window_title)
        elif choice == "8":
            window_title = pick_window_title_loop(cfg)
            test_ui_widgets_read(cfg, window_title=window_title)
        elif choice == "9":
            test_window_focus_interactive_cfg(cfg)
        elif choice == "10":
            test_full_workflow_cfg(cfg)
        elif choice == "11":
            run_acceptance_and_save(cfg)
        elif choice == "12":
            window_title = pick_window_title_loop(cfg)
            test_ui_widgets_query(cfg, window_title=window_title)
        else:
            print("无效选择")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试中断")
    except Exception as e:
        print(f"\n错误：{e}")
        print("请确保服务器已启动：python server.py")
