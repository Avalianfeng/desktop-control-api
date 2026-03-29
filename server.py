"""
Desktop Control API Server
为 AI 代理提供的统一桌面自动化 API 服务
"""

import asyncio
import hashlib
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Response, Security
from fastapi.requests import Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
import uvicorn

from controllers.ocr_routes import build_vision_router, build_visual_router
from deps import Deps, create_default_deps
from errors import ApiError
from models.ui_dom import UIReadOptions
from semantic.widget_builder import build_widgets
from semantic.widget_types import ACTIONABLE_WIDGET_ROLES, WidgetResponse, WidgetStats
from traceability.action_traces import append_trace_event, new_trace_id
from settings import DEFAULT_API_KEY, Settings, default_ui_max_depth
from query.api_mapping import to_engine_filters
from observability.context import set_request_id
from observability.logging import configure_logging, log_extra
from observability.metrics import (
    HTTP_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_MS,
    DESKTOP_ACTION_ATTEMPTS_TOTAL,
    DESKTOP_ACTION_DURATION_MS,
    safe_route_label,
)
from observability.tracing import configure_tracing, set_span_attributes, start_span
from response_envelope import fail, ok, wants_raw_response
from controllers.win32_win import get_foreground_hwnd
from controllers.win32_window_capture import configure_process_dpi_awareness

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # type: ignore
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None  # type: ignore

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
except Exception:  # pragma: no cover
    FastAPIInstrumentor = None  # type: ignore

# ============== 配置 ==============
settings = Settings.from_env()
configure_logging(level=settings.log_level)
configure_tracing(service_name="desktop-control-api")
logger = logging.getLogger("desktop-control-api")

_dpi_aware = configure_process_dpi_awareness()
if not _dpi_aware.get("ok"):
    logger.warning(
        "process_dpi_awareness_not_set",
        extra=log_extra(
            op="startup",
            reason=str(_dpi_aware.get("reason") or "unknown"),
            hint="窗口截图 PrintWindow 与 GetClientRect 在高 DPI 下建议 Per-Monitor v2",
        ),
    )

deps = create_default_deps()

# API Key 安全认证
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
VALID_API_KEYS = list(settings.api_keys)

# Back-compat aliases (tests monkeypatch these)
action_lock = deps.action_lock
screenshot_ctrl = deps.screenshot_ctrl
mouse_ctrl = deps.mouse_ctrl
keyboard_ctrl = deps.keyboard_ctrl
windows_ctrl = deps.windows_ctrl
locator_ctrl = deps.locator_ctrl
ui_read_ctrl = deps.ui_read_ctrl
widget_query_ctrl = deps.widget_query_ctrl
widget_action_ctrl = deps.widget_action_ctrl


def create_app(*, settings: Settings, deps: Deps) -> FastAPI:
    app = FastAPI(
        title="Desktop Control API",
        description="为 AI 代理提供的统一桌面自动化 API 服务",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = settings
    app.state.deps = deps
    if FastAPIInstrumentor is not None:
        try:
            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            pass

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-redef]
        incoming = (request.headers.get("X-Request-Id") or "").strip()
        request_id = incoming if (0 < len(incoming) <= 64) else secrets.token_hex(8)
        request.state.request_id = request_id
        set_request_id(request_id)

        timer_start = time.perf_counter()
        method = request.method
        route_tpl = None
        try:
            route = request.scope.get("route")
            route_tpl = getattr(route, "path", None)
        except Exception:
            route_tpl = None
        route_label = safe_route_label(route_tpl, str(request.url.path))

        HTTP_IN_FLIGHT.labels(method=method, route=route_label).inc()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            elapsed_ms = int((time.perf_counter() - timer_start) * 1000)
            HTTP_IN_FLIGHT.labels(method=method, route=route_label).dec()
            HTTP_REQUESTS_TOTAL.labels(method=method, route=route_label, status_code=str(status_code)).inc()
            HTTP_REQUEST_DURATION_MS.labels(method=method, route=route_label, status_code=str(status_code)).observe(
                elapsed_ms
            )
            set_span_attributes(
                request_id=request_id,
                http_route=route_label,
                http_method=method,
                http_status_code=status_code,
                duration_ms=elapsed_ms,
            )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):  # type: ignore[no-redef]
        rid = getattr(request.state, "request_id", None)
        tid = getattr(request.state, "trace_id", None)
        if exc.status_code >= 500:
            logger.exception(
                "api_error",
                extra=log_extra(
                    op="api_error",
                    request_id=rid,
                    code=exc.code,
                    status_code=exc.status_code,
                    details=exc.details,
                ),
                exc_info=exc.cause or exc,
            )
        else:
            logger.warning(
                "api_error",
                extra=log_extra(
                    op="api_error",
                    request_id=rid,
                    code=exc.code,
                    status_code=exc.status_code,
                    details=exc.details,
                ),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(
                code=exc.code,
                message=exc.message,
                request_id=rid,
                trace_id=tid,
                details=exc.details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-redef]
        rid = getattr(request.state, "request_id", None)
        tid = getattr(request.state, "trace_id", None)
        message = str(exc.detail) if exc.detail is not None else "请求失败"
        level = logging.WARNING if 400 <= exc.status_code < 500 else logging.ERROR
        logger.log(
            level,
            "http_exception",
            extra=log_extra(
                op="http_exception",
                request_id=rid,
                status_code=exc.status_code,
                detail=message,
            ),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(code="http_error", message=message, request_id=rid, trace_id=tid),
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):  # type: ignore[no-redef]
        rid = getattr(request.state, "request_id", None)
        tid = getattr(request.state, "trace_id", None)
        message = str(exc) or "资源不存在"
        logger.warning(
            "file_not_found",
            extra=log_extra(op="file_not_found", request_id=rid, detail=message),
        )
        return JSONResponse(
            status_code=404,
            content=fail(code="not_found", message=message, request_id=rid, trace_id=tid),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):  # type: ignore[no-redef]
        rid = getattr(request.state, "request_id", None)
        tid = getattr(request.state, "trace_id", None)
        logger.exception(
            "unhandled_error",
            extra=log_extra(op="unhandled_error", request_id=rid),
        )
        return JSONResponse(
            status_code=500,
            content=fail(code="internal_error", message="服务内部错误", request_id=rid, trace_id=tid),
        )

    return app


app = create_app(settings=settings, deps=deps)

async def verify_api_key(api_key: str | None = Security(api_key_header)):
    if not api_key:
        raise ApiError(status_code=403, code="auth_missing_api_key", message="缺少 API Key")

    if not any(secrets.compare_digest(api_key, valid_key) for valid_key in VALID_API_KEYS):
        raise ApiError(status_code=403, code="auth_invalid_api_key", message="API Key 无效")
    return api_key


app.include_router(build_visual_router(deps))
app.include_router(build_vision_router(deps))


def ensure_region(region: Optional[List[int]], name: str = "region") -> Optional[List[int]]:
    """Validate region format [x, y, width, height]."""
    if region is None:
        return None

    if len(region) != 4:
        raise HTTPException(status_code=400, detail=f"{name} 必须是 [x, y, width, height]")

    x, y, width, height = region
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail=f"{name} 的 width 和 height 必须大于 0")
    if x < 0 or y < 0:
        raise HTTPException(status_code=400, detail=f"{name} 的 x 和 y 不能为负数")

    return region


def _validate_non_negative_coordinate(value: int) -> int:
    if value < 0:
        raise ValueError("坐标不能为负数")
    return value


async def run_desktop_action(
    endpoint: str,
    action: Callable[[], Any],
    payload: Optional[Dict[str, Any]] = None,
    *,
    lock: asyncio.Lock | None = action_lock,
) -> Any:
    """Run potentially blocking desktop actions in a serialized and logged way."""
    start = time.perf_counter()
    redacted_payload = _redact_payload_for_log(endpoint, payload)
    try:
        with start_span("desktop_action"):
            set_span_attributes(op="desktop_action", endpoint=endpoint)
            if lock is None:
                result = await asyncio.to_thread(action)
            else:
                async with lock:
                    result = await asyncio.to_thread(action)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        DESKTOP_ACTION_ATTEMPTS_TOTAL.labels(endpoint=endpoint, success="true").inc()
        DESKTOP_ACTION_DURATION_MS.labels(endpoint=endpoint, success="true").observe(elapsed_ms)
        logger.info(
            "desktop_action",
            extra=log_extra(
                op="desktop_action",
                endpoint=endpoint,
                success=True,
                duration_ms=elapsed_ms,
                payload=redacted_payload,
            ),
        )
        return result
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        DESKTOP_ACTION_ATTEMPTS_TOTAL.labels(endpoint=endpoint, success="false").inc()
        DESKTOP_ACTION_DURATION_MS.labels(endpoint=endpoint, success="false").observe(elapsed_ms)
        logger.exception(
            "desktop_action_failed",
            extra=log_extra(
                op="desktop_action",
                endpoint=endpoint,
                success=False,
                duration_ms=elapsed_ms,
                payload=redacted_payload,
                error_type=type(exc).__name__,
            ),
        )
        raise


def _redact_payload_for_log(endpoint: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return {}
    if endpoint == "/locate/text":
        redacted = dict(payload)
        txt = redacted.pop("text", None)
        txt_s = txt if isinstance(txt, str) else ""
        redacted["text_len"] = len(txt_s)
        redacted["text_sha256_8"] = hashlib.sha256(txt_s.encode("utf-8")).hexdigest()[:8] if txt_s else None
        return redacted
    return payload


async def api_action(
    *,
    endpoint: str,
    action: Callable[[], Any],
    payload: Optional[Dict[str, Any]] = None,
    error_prefix: str,
    lock: asyncio.Lock | None = action_lock,
) -> Any:
    try:
        return await run_desktop_action(endpoint, action, payload=payload, lock=lock)
    except (HTTPException, ApiError):
        raise
    except Exception as e:
        raise ApiError(status_code=500, code="action_failed", message=f"{error_prefix}：{str(e)}", cause=e)

# ============== 数据模型 ==============

# 鼠标操作
class MouseClickRequest(BaseModel):
    x: int = Field(..., description="X 坐标")
    y: int = Field(..., description="Y 坐标")
    button: str = Field(default="left", description="按钮：left/right/middle", pattern="^(left|right|middle)$")
    clicks: int = Field(default=1, ge=1, le=10, description="点击次数（1=单击，2=双击）")

    @field_validator("x", "y")
    @classmethod
    def validate_non_negative_coordinates(cls, value: int) -> int:
        return _validate_non_negative_coordinate(value)

class MouseMoveRequest(BaseModel):
    x: int = Field(..., description="目标 X 坐标")
    y: int = Field(..., description="目标 Y 坐标")
    duration: float = Field(default=0.5, ge=0, le=10, description="移动时间（秒）")

    @field_validator("x", "y")
    @classmethod
    def validate_non_negative_coordinates(cls, value: int) -> int:
        return _validate_non_negative_coordinate(value)

class MouseDragRequest(BaseModel):
    start_x: int = Field(..., description="起始 X 坐标")
    start_y: int = Field(..., description="起始 Y 坐标")
    end_x: int = Field(..., description="结束 X 坐标")
    end_y: int = Field(..., description="结束 Y 坐标")
    duration: float = Field(default=0.5, ge=0, le=10, description="拖拽时间（秒）")

    @field_validator("start_x", "start_y", "end_x", "end_y")
    @classmethod
    def validate_non_negative_coordinates(cls, value: int) -> int:
        return _validate_non_negative_coordinate(value)

class MouseScrollRequest(BaseModel):
    x: Optional[int] = Field(default=None, description="滚动中心 X 坐标（默认屏幕中心）")
    y: Optional[int] = Field(default=None, description="滚动中心 Y 坐标（默认屏幕中心）")
    amount: int = Field(default=0, ge=-120, le=120, description="垂直滚动量（正数向上，负数向下）")
    horizontal: int = Field(default=0, ge=-120, le=120, description="水平滚动量（正数向右，负数向左）")
    duration: float = Field(default=0.1, ge=0, le=2, description="滚动前移动耗时（秒）")

    @field_validator("x", "y")
    @classmethod
    def validate_optional_coordinate(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("坐标不能为负数")
        return value

# 键盘操作
class KeyboardTypeRequest(BaseModel):
    text: str = Field(..., description="要输入的文本")
    interval: float = Field(default=0.05, ge=0, le=2, description="字符间隔（秒）")
    target_hwnd: int = Field(..., ge=1, description="目标窗口 hwnd（必填，避免输入到错误窗口）")
    delay_ms: int = Field(default=0, ge=0, le=60_000, description="切换焦点后的延迟（毫秒）")

class KeyboardPressRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=30, description="按键名称（enter, tab, escape 等）")

class KeyboardHotkeyRequest(BaseModel):
    keys: List[str] = Field(..., min_length=1, max_length=6, description="快捷键组合（如 ['ctrl', 'c']）")

    @field_validator("keys")
    @classmethod
    def validate_hotkey_parts(cls, value: List[str]) -> List[str]:
        if not all(part.strip() for part in value):
            raise ValueError("快捷键中不能包含空字符串")
        return value

# 窗口操作
class WindowFocusRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300, description="窗口标题（部分匹配，可选）")
    hwnd: Optional[int] = Field(default=None, ge=1, description="窗口 hwnd（推荐，唯一标识）")
    title_match_index: int = Field(
        default=0,
        ge=0,
        description="标题子串匹配到多个窗口时的下标（0 起）；仅与 title 一起使用",
    )
    best_effort: bool = Field(
        default=False,
        description=(
            "为 True 时：系统拒绝置前仍返回 HTTP 200，data.focused=false，不抛 409。"
            "适用于仅需 hwnd 做 UIA 查询 / PrintWindow 截图等、不强依赖前台的场景。"
        ),
    )

class WindowMoveRequest(BaseModel):
    title: str = Field(..., description="窗口标题")
    x: int = Field(..., description="新 X 坐标")
    y: int = Field(..., description="新 Y 坐标")
    width: Optional[int] = Field(default=None, description="新宽度")
    height: Optional[int] = Field(default=None, description="新高度")

    @field_validator("x", "y")
    @classmethod
    def validate_non_negative_coordinates(cls, value: int) -> int:
        return _validate_non_negative_coordinate(value)

    @field_validator("width", "height")
    @classmethod
    def validate_positive_size(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("宽高必须大于 0")
        return value

# 元素定位
class LocateImageRequest(BaseModel):
    image_path: str = Field(..., description="要查找的图像路径")
    confidence: float = Field(default=0.8, ge=0, le=1, description="匹配置信度（0-1）")
    screen_region: Optional[List[int]] = Field(default=None, description="搜索区域 [x, y, width, height]")

class LocateTextRequest(BaseModel):
    text: str = Field(..., description="要查找的文字")
    screen_region: Optional[List[int]] = Field(default=None, description="搜索区域 [x, y, width, height]")

# 截图增强
class ScreenshotWindowRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300, description="窗口标题（部分匹配）")
    include_decorations: bool = Field(default=False, description="是否包含标题栏和边框")
    scale: float = Field(default=1.0, ge=0.1, le=2.0, description="缩放比例（0.1-2.0）")
    include_image: bool = Field(
        default=False, description="是否在响应中包含 base64 image（默认 false，与 /screenshot 一致）"
    )


class ScreenshotRegionRequest(BaseModel):
    x: int = Field(..., ge=0, description="区域起点 X")
    y: int = Field(..., ge=0, description="区域起点 Y")
    width: int = Field(..., gt=0, description="区域宽度")
    height: int = Field(..., gt=0, description="区域高度")
    scale: float = Field(default=1.0, ge=0.1, le=2.0, description="缩放比例（0.1-2.0）")
    include_image: bool = Field(
        default=False, description="是否在响应中包含 base64 image（默认 false，与其它截图端点一致）"
    )


class UIDOMReadRequest(BaseModel):
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选，不传则读取当前活动窗口）")
    window_hwnd: Optional[int] = Field(default=None, ge=1, description="窗口 hwnd（可选，优先）")
    max_depth: int = Field(
        default_factory=default_ui_max_depth, ge=1, le=30, description="UI 树最大深度（默认见 .env DESKTOP_UI_MAX_DEPTH）"
    )
    include_offscreen: bool = Field(default=False, description="是否包含屏幕外元素")
    include_disabled: bool = Field(default=True, description="是否包含不可用元素")
    include_invisible: bool = Field(default=False, description="是否包含不可见元素")
    include_semantic: bool = Field(default=True, description="是否生成 Semantic DOM（过滤后的精简列表）")
    semantic_include_text_labels: bool = Field(
        default=False, description="Semantic 中是否额外包含可见文本节点（非可操作）"
    )


class UIWidgetsReadRequest(BaseModel):
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选，不传则读取当前活动窗口）")
    window_hwnd: Optional[int] = Field(default=None, ge=1, description="窗口 hwnd（可选，优先）")
    max_depth: int = Field(
        default_factory=default_ui_max_depth, ge=1, le=30, description="UI 树最大深度（默认见 .env DESKTOP_UI_MAX_DEPTH）"
    )
    include_offscreen: bool = Field(default=False, description="是否包含屏幕外元素")
    include_disabled: bool = Field(default=True, description="是否包含不可用元素")
    include_invisible: bool = Field(default=False, description="是否包含不可见元素")
    include_text_widgets: bool = Field(default=True, description="widgets 中是否包含文本节点")
    collapse_icons: bool = Field(default=True, description="是否将 \\ufxxx 等 icon 字符映射为语义 token（最小集合）")


class WidgetQueryRegion(BaseModel):
    preset: Optional[Literal["top_half", "bottom_half", "left_half", "right_half", "center"]] = Field(
        default=None, description="区域预设（按 window 框计算）"
    )
    rect: Optional[List[int]] = Field(default=None, description="自定义区域 [x, y, width, height]")


class WidgetQueryFilters(BaseModel):
    role: Optional[str] = None
    normalized: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    visible: Optional[bool] = None
    focusable: Optional[bool] = None
    text_contains: Optional[str] = None
    ancestor_role: Optional[str] = None
    region: Optional[WidgetQueryRegion] = None


class UIWidgetsQueryRequest(BaseModel):
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选，不传则读取当前活动窗口）")
    window_hwnd: Optional[int] = Field(default=None, ge=1, description="窗口 hwnd（可选，优先）")
    max_depth: int = Field(
        default_factory=default_ui_max_depth, ge=1, le=30, description="UI 树最大深度（默认见 .env DESKTOP_UI_MAX_DEPTH）"
    )
    include_offscreen: bool = Field(default=False, description="是否包含屏幕外元素")
    include_disabled: bool = Field(default=True, description="是否包含不可用元素")
    include_invisible: bool = Field(default=False, description="是否包含不可见元素")
    include_text_widgets: bool = Field(default=True, description="widgets 中是否包含文本节点")
    collapse_icons: bool = Field(default=True, description="是否将 \\ufxxx 等 icon 字符映射为语义 token（最小集合）")
    filters: WidgetQueryFilters = Field(default_factory=WidgetQueryFilters)
    limit: int = Field(default=50, ge=0, le=500, description="最多返回多少条 widgets")
    select: List[str] = Field(
        default_factory=lambda: ["id", "role", "normalized", "text", "bounds"],
        description="返回字段白名单裁剪",
    )


class UIWidgetClickRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=200, description="widget id（稳定 locator）")
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选，不传则使用当前活动窗口）")
    max_depth: int = Field(
        default_factory=default_ui_max_depth, ge=1, le=30, description="UI 树最大深度（默认见 .env DESKTOP_UI_MAX_DEPTH）"
    )
    fingerprint: Optional[Dict[str, object]] = Field(default=None, description="可选 fingerprint（用于找不到 id 时重定位）")
    target_hwnd: Optional[int] = Field(default=None, ge=1, description="目标窗口 hwnd（可选；提供则先确保焦点在该窗口）")


class UIWidgetSetValueRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=200, description="widget id（稳定 locator）")
    value: str = Field(..., description="要设置的文本值")
    verify: bool = Field(default=False, description="是否回读验证 value 是否生效（默认 false）")
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选，不传则使用当前活动窗口）")
    max_depth: int = Field(
        default_factory=default_ui_max_depth, ge=1, le=30, description="UI 树最大深度（默认见 .env DESKTOP_UI_MAX_DEPTH）"
    )
    fingerprint: Optional[Dict[str, object]] = Field(default=None, description="可选 fingerprint（用于找不到 id 时重定位）")
    target_hwnd: Optional[int] = Field(default=None, ge=1, description="目标窗口 hwnd（可选；提供则先确保焦点在该窗口）")


class WidgetActRequest(BaseModel):
    """POST /widgets/act 白名单：click | set_value（与 AI_PROTOCOL 对齐）。"""

    action: Literal["click", "set_value"]
    id: str = Field(..., min_length=1, max_length=200, description="widget id")
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选）")
    max_depth: int = Field(default_factory=default_ui_max_depth, ge=1, le=30)
    fingerprint: Optional[Dict[str, object]] = Field(default=None)
    target_hwnd: Optional[int] = Field(default=None, ge=1)
    value: Optional[str] = Field(default=None, description="仅 action=set_value")
    verify: bool = Field(default=False, description="仅 set_value")

    @model_validator(mode="after")
    def _require_value_for_set(self) -> "WidgetActRequest":
        if self.action == "set_value" and self.value is None:
            raise ValueError("action=set_value 时必须提供 value")
        return self

# ============== API 路由 ==============

@app.get("/health")
async def health_check():
    """健康检查"""
    return ok(data={"status": "ok", "message": "Desktop Control API 运行中"}, trace_id=None)


@app.get("/livez")
async def liveness_probe():
    return ok(data={"status": "ok"}, trace_id=None)


@app.get("/readyz")
async def readiness_probe(request: Request):
    """
    readiness 需要真实反映服务能力：若关键依赖不可用，应返回非 200。
    该服务的关键能力依赖于：窗口枚举 + UIAutomation 可访问。
    """
    d: Deps = request.app.state.deps
    # 1) 基础依赖：能枚举窗口（不要求非空，允许无窗口标题等场景）
    try:
        windows = await asyncio.wait_for(asyncio.to_thread(d.windows_ctrl.list_all), timeout=1.0)
    except Exception as exc:
        logger.warning(
            "readiness_failed",
            extra=log_extra(op="readiness", step="list_windows", error_type=type(exc).__name__),
        )
        return JSONResponse(
            status_code=503,
            content=fail(code="not_ready", message="list_windows_failed", details={"status": "not_ready", "reason": "list_windows_failed"}),
        )

    # 2) UIA 轻量探针：确认 uiautomation 可用 + 活动窗口句柄可访问
    try:
        probe = await asyncio.wait_for(asyncio.to_thread(d.ui_read_ctrl.uia_source.probe), timeout=1.0)
    except Exception as exc:
        logger.warning(
            "readiness_failed",
            extra=log_extra(op="readiness", step="uia_probe", error_type=type(exc).__name__),
        )
        return JSONResponse(
            status_code=503,
            content=fail(code="not_ready", message="uia_probe_failed", details={"status": "not_ready", "reason": "uia_probe_failed"}),
        )

    if not probe.get("ok"):
        logger.warning(
            "readiness_degraded",
            extra=log_extra(op="readiness", step="uia_probe", probe=probe),
        )
        return JSONResponse(
            status_code=503,
            content=fail(
                code="not_ready",
                message=str(probe.get("reason") or "not_ready"),
                details={"status": "not_ready", "reason": probe.get("reason"), "probe": probe},
            ),
        )

    return ok(data={"status": "ok", "windows_seen": len(windows), "uia": probe}, trace_id=None)


@app.get("/metrics")
async def metrics_endpoint(request: Request):
    if generate_latest is None:
        return JSONResponse(status_code=501, content=fail(code="metrics_unavailable", message="未安装 prometheus_client"))
    data = generate_latest()
    if wants_raw_response(request):
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    text = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
    return ok(data={"content_type": CONTENT_TYPE_LATEST, "text": text}, trace_id=None)


@app.on_event("startup")
async def startup_checks():
    if DEFAULT_API_KEY in VALID_API_KEYS:
        if not settings.allow_insecure_default_key:
            raise RuntimeError(
                "检测到正在使用默认 API Key。请设置 DESKTOP_API_KEY 或 DESKTOP_API_KEYS；"
                "如需临时允许默认 key，请设置 DESKTOP_ALLOW_INSECURE_DEFAULT_KEY=1。"
            )
        logger.warning("正在使用默认 API Key（已显式允许）。生产环境请设置 DESKTOP_API_KEY 或 DESKTOP_API_KEYS。")
    logger.info(
        "Desktop Control API started host=%s port=%s key_count=%s",
        settings.host,
        settings.port,
        len(VALID_API_KEYS),
    )

@app.post("/screenshot", dependencies=[Security(verify_api_key)])
async def take_screenshot(
    region: Optional[List[int]] = Query(default=None, description="截图区域 [x, y, width, height]"),
    include_image: bool = Query(default=False, description="是否在响应中包含 base64 image（默认 false，避免 token 爆炸）"),
):
    """
    截取屏幕截图
    - 不传 region：全屏截图
    - 传 region：截取指定区域
    v1.6：固定落盘到 updates/screenshots/<UTC 日期>/ 并返回 path 元数据；可用 include_image=1 显式返回 base64。
    """
    validated_region = ensure_region(region)
    file_meta = await api_action(
        endpoint="/screenshot",
        action=lambda: screenshot_ctrl.capture_to_file(region=validated_region),
        payload={"region": validated_region, "include_image": bool(include_image)},
        error_prefix="截图失败",
        lock=None,  # 只读
    )
    data = {
        "format": file_meta["format"],
        "width": file_meta["width"],
        "height": file_meta["height"],
        "path": file_meta["path"],
        "bytes": file_meta["bytes"],
        "sha256_8": file_meta["sha256_8"],
    }
    if include_image:
        # best-effort: reuse capture() base64 for backward compatibility
        image_data = await api_action(
            endpoint="/screenshot",
            action=lambda: screenshot_ctrl.capture(region=validated_region),
            payload={"region": validated_region},
            error_prefix="截图失败",
            lock=None,
        )
        data["image"] = image_data["base64"]
    return ok(
        data=data,
        trace_id=None,
    )

@app.post("/mouse/click", dependencies=[Security(verify_api_key)])
async def mouse_click(request: MouseClickRequest):
    """鼠标点击"""
    await api_action(
        endpoint="/mouse/click",
        action=lambda: mouse_ctrl.click(request.x, request.y, button=request.button, clicks=request.clicks),
        payload={"x": request.x, "y": request.y, "button": request.button, "clicks": request.clicks},
        error_prefix="鼠标点击失败",
        lock=action_lock,
    )
    return ok(data={"action": "click", "position": [request.x, request.y]}, trace_id=None)

@app.post("/mouse/move", dependencies=[Security(verify_api_key)])
async def mouse_move(request: MouseMoveRequest):
    """鼠标移动"""
    await api_action(
        endpoint="/mouse/move",
        action=lambda: mouse_ctrl.move(request.x, request.y, duration=request.duration),
        payload={"x": request.x, "y": request.y, "duration": request.duration},
        error_prefix="鼠标移动失败",
        lock=action_lock,
    )
    return ok(data={"action": "move", "position": [request.x, request.y]}, trace_id=None)

@app.post("/mouse/drag", dependencies=[Security(verify_api_key)])
async def mouse_drag(request: MouseDragRequest):
    """鼠标拖拽"""
    await api_action(
        endpoint="/mouse/drag",
        action=lambda: mouse_ctrl.drag(
            request.start_x,
            request.start_y,
            request.end_x,
            request.end_y,
            duration=request.duration,
        ),
        payload={
            "start_x": request.start_x,
            "start_y": request.start_y,
            "end_x": request.end_x,
            "end_y": request.end_y,
            "duration": request.duration,
        },
        error_prefix="鼠标拖拽失败",
        lock=action_lock,
    )
    return ok(
        data={
            "action": "drag",
            "start": [request.start_x, request.start_y],
            "end": [request.end_x, request.end_y],
        },
        trace_id=None,
    )


@app.post("/mouse/scroll", dependencies=[Security(verify_api_key)])
async def mouse_scroll(request: MouseScrollRequest):
    """鼠标滚轮（支持垂直/水平滚动）"""
    if request.amount == 0 and request.horizontal == 0:
        raise HTTPException(status_code=400, detail="amount 和 horizontal 不能同时为 0")
    await api_action(
        endpoint="/mouse/scroll",
        action=lambda: mouse_ctrl.scroll(
            amount=request.amount,
            x=request.x,
            y=request.y,
            horizontal=request.horizontal,
            duration=request.duration,
        ),
        payload={
            "x": request.x,
            "y": request.y,
            "amount": request.amount,
            "horizontal": request.horizontal,
            "duration": request.duration,
        },
        error_prefix="鼠标滚动失败",
        lock=action_lock,
    )
    return ok(
        data={
            "action": "scroll",
            "position": {"x": request.x, "y": request.y},
            "vertical_amount": request.amount,
            "horizontal_amount": request.horizontal,
        },
        trace_id=None,
    )

@app.post("/keyboard/type", dependencies=[Security(verify_api_key)])
async def keyboard_type(request: KeyboardTypeRequest, http_request: Request):
    """键盘输入文本"""

    def _do() -> None:
        active_hwnd = windows_ctrl.get_active_hwnd()
        if active_hwnd != int(request.target_hwnd):
            focused, ferr = windows_ctrl.focus_by_hwnd(int(request.target_hwnd))
            if not focused:
                if ferr == "focus_failed":
                    raise ApiError(
                        status_code=409,
                        code="window_focus_failed",
                        message=f"窗口存在但无法激活或置前：hwnd={request.target_hwnd}",
                    )
                raise HTTPException(status_code=404, detail=f"未找到窗口：hwnd={request.target_hwnd}")
        if request.delay_ms:
            time.sleep(request.delay_ms / 1000.0)

        fg = get_foreground_hwnd()
        if fg and fg != int(request.target_hwnd):
            raise ApiError(
                status_code=409,
                code="window_focus_failed",
                message=f"窗口未处于前台，拒绝输入：target_hwnd={request.target_hwnd} foreground_hwnd={fg}",
                details={"target_hwnd": int(request.target_hwnd), "foreground_hwnd": int(fg)},
            )
        keyboard_ctrl.type_text(request.text, interval=request.interval)

    trace_id = new_trace_id()
    http_request.state.trace_id = trace_id
    t0 = time.perf_counter()
    await api_action(
        endpoint="/keyboard/type",
        action=_do,
        payload={
            "text_length": len(request.text),
            "interval": request.interval,
            "target_hwnd": int(request.target_hwnd),
            "delay_ms": int(request.delay_ms),
        },
        error_prefix="键盘输入失败",
        lock=action_lock,
    )
    duration_ms = int((time.perf_counter() - t0) * 1000)
    actor = (http_request.headers.get("X-Actor") or "").strip() or None
    api_key = (http_request.headers.get("X-API-Key") or "").strip()
    api_key_sha256_8 = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8] if api_key else None
    append_trace_event(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "endpoint": "/keyboard/type",
            "mode": "live",
            "actor": actor,
            "api_key_sha256_8": api_key_sha256_8,
            "hwnd": int(request.target_hwnd),
            "stable_id": None,
            "resolved": None,
            "resolved_by": None,
            "verified": None,
            "verify_reason": None,
            "duration_ms": duration_ms,
            "success": True,
            "error_code": None,
        }
    )
    return ok(data={"action": "type", "length": len(request.text)}, trace_id=trace_id)

@app.post("/keyboard/press", dependencies=[Security(verify_api_key)])
async def keyboard_press(request: KeyboardPressRequest):
    """键盘按键"""
    await api_action(
        endpoint="/keyboard/press",
        action=lambda: keyboard_ctrl.press(request.key),
        payload={"key": request.key},
        error_prefix="键盘按键失败",
        lock=action_lock,
    )
    return ok(data={"action": "press", "key": request.key}, trace_id=None)

@app.post("/keyboard/hotkey", dependencies=[Security(verify_api_key)])
async def keyboard_hotkey(request: KeyboardHotkeyRequest):
    """键盘快捷键"""
    await api_action(
        endpoint="/keyboard/hotkey",
        action=lambda: keyboard_ctrl.hotkey(request.keys),
        payload={"keys": request.keys},
        error_prefix="快捷键失败",
        lock=action_lock,
    )
    return ok(data={"action": "hotkey", "keys": request.keys}, trace_id=None)

@app.get("/windows", dependencies=[Security(verify_api_key)])
async def list_windows(
    raw: bool = Query(default=False, description="调试模式：返回完整未过滤窗口列表（含诊断字段）"),
    include_system: bool = Query(default=False, description="同 raw=1：返回完整未过滤窗口列表（含诊断字段）"),
):
    """列出窗口（默认仅返回可交互窗口以节省 token；raw/include_system 返回完整列表用于排障）"""
    want_full = bool(raw or include_system)
    windows = await api_action(
        endpoint="/windows",
        action=(windows_ctrl.list_all if want_full else windows_ctrl.list_interactive),
        error_prefix="获取窗口列表失败",
        lock=None,  # 只读
    )
    return ok(data={"count": len(windows), "windows": windows}, trace_id=None)

@app.post("/windows/focus", dependencies=[Security(verify_api_key)])
async def window_focus(request: WindowFocusRequest):
    """聚焦/激活窗口"""
    if request.hwnd is not None:
        result, err = await api_action(
            endpoint="/windows/focus",
            action=lambda: windows_ctrl.focus_by_hwnd(int(request.hwnd or 0)),
            payload={"hwnd": int(request.hwnd or 0)},
            error_prefix="窗口聚焦失败",
            lock=action_lock,
        )
        if err is None and result:
            return ok(
                data={"action": "focus", "focused": True, "window": result},
                trace_id=None,
            )
        if err == "focus_failed":
            if request.best_effort:
                return ok(
                    data={
                        "action": "focus",
                        "focused": False,
                        "reason": "focus_failed",
                        "window": None,
                        "hwnd": int(request.hwnd),
                    },
                    trace_id=None,
                )
            raise ApiError(
                status_code=409,
                code="window_focus_failed",
                message=f"窗口存在但无法激活或置前：hwnd={request.hwnd}",
            )
        raise HTTPException(status_code=404, detail=f"未找到窗口：hwnd={request.hwnd}")

    title = (request.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title 或 hwnd 必须至少提供一个")

    idx = int(request.title_match_index)
    result, err = await api_action(
        endpoint="/windows/focus",
        action=lambda: windows_ctrl.focus(title, title_match_index=idx),
        payload={"title": title, "title_match_index": idx},
        error_prefix="窗口聚焦失败",
        lock=action_lock,
    )
    if err is None and result:
        return ok(
            data={"action": "focus", "focused": True, "window": result},
            trace_id=None,
        )
    if err == "focus_failed":
        if request.best_effort:
            return ok(
                data={
                    "action": "focus",
                    "focused": False,
                    "reason": "focus_failed",
                    "window": None,
                    "title": title,
                    "title_match_index": idx,
                },
                trace_id=None,
            )
        raise ApiError(
            status_code=409,
            code="window_focus_failed",
            message=f"窗口存在但无法激活或置前：{title} (index={idx})",
        )
    raise HTTPException(status_code=404, detail=f"未找到窗口：{title}")

@app.post("/windows/move", dependencies=[Security(verify_api_key)])
async def window_move(request: WindowMoveRequest):
    """移动/调整窗口"""
    result = await api_action(
        endpoint="/windows/move",
        action=lambda: windows_ctrl.move(
            request.title,
            request.x,
            request.y,
            width=request.width,
            height=request.height,
        ),
        payload={
            "title": request.title,
            "x": request.x,
            "y": request.y,
            "width": request.width,
            "height": request.height,
        },
        error_prefix="窗口移动失败",
        lock=action_lock,
    )
    if result:
        return ok(data={"action": "move", "window": result}, trace_id=None)
    raise HTTPException(status_code=404, detail=f"未找到窗口：{request.title}")

if bool(getattr(settings, "expose_debug_routes", False)):
    @app.post("/locate/image", dependencies=[Security(verify_api_key)])
    async def locate_image(request: LocateImageRequest):
        """图像定位（在屏幕上找图）。调试/诊断用途：默认不暴露。"""
        validated_region = ensure_region(request.screen_region, name="screen_region")
        if not os.path.exists(request.image_path):
            raise HTTPException(status_code=404, detail=f"图像文件不存在：{request.image_path}")

        result = await api_action(
            endpoint="/locate/image",
            action=lambda: locator_ctrl.locate_image(
                request.image_path,
                confidence=request.confidence,
                region=validated_region,
            ),
            payload={"image_path": request.image_path, "confidence": request.confidence, "screen_region": validated_region},
            error_prefix="图像定位失败",
            lock=None,  # 只读
        )
        if result:
            return ok(data={"found": True, "location": result}, trace_id=None)
        return ok(data={"found": False, "message": "未找到匹配图像"}, trace_id=None)

    @app.post("/locate/text", dependencies=[Security(verify_api_key)])
    async def locate_text(request: LocateTextRequest):
        """文字定位（OCR 查找文字）。调试/诊断用途：默认不暴露。"""
        validated_region = ensure_region(request.screen_region, name="screen_region")
        result = await api_action(
            endpoint="/locate/text",
            action=lambda: locator_ctrl.locate_text(request.text, region=validated_region),
            payload={"text": request.text, "screen_region": validated_region},
            error_prefix="文字定位失败",
            lock=None,  # 只读
        )
        if result:
            return ok(data={"found": True, "location": result}, trace_id=None)
        return ok(data={"found": False, "message": f"未找到文字：{request.text}"}, trace_id=None)


@app.post("/screenshot/window", dependencies=[Security(verify_api_key)])
async def screenshot_window(request: ScreenshotWindowRequest):
    """
    按窗口标题截图。
    v1.6+：固定落盘（与 /screenshot 相同目录）并返回 path；include_image=true 时额外返回 base64。
    """
    result = await api_action(
        endpoint="/screenshot/window",
        action=lambda: screenshot_ctrl.capture_window(
            request.title,
            include_decorations=request.include_decorations,
            scale=request.scale,
            include_image=request.include_image,
        ),
        payload={
            "title": request.title,
            "include_decorations": request.include_decorations,
            "scale": request.scale,
            "include_image": bool(request.include_image),
        },
        error_prefix="窗口截图失败",
        lock=None,  # 只读
    )
    data = {
        "format": result["format"],
        "width": result["width"],
        "height": result["height"],
        "path": result["path"],
        "bytes": result["bytes"],
        "sha256_8": result["sha256_8"],
        "window": result["window"],
        "capture_method": result.get("capture_method", "unknown"),
    }
    if request.include_image:
        data["image"] = result["image"]
    return ok(data=data, trace_id=None)


@app.post("/screenshot/region", dependencies=[Security(verify_api_key)])
async def screenshot_region(request: ScreenshotRegionRequest):
    """
    按请求体参数截取屏幕矩形（mss），固定目录落盘；默认返回 path 元数据，include_image=true 时额外返回 base64。
    """
    result = await api_action(
        endpoint="/screenshot/region",
        action=lambda: screenshot_ctrl.capture_region(
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
            scale=request.scale,
            include_image=request.include_image,
        ),
        payload={
            "x": request.x,
            "y": request.y,
            "width": request.width,
            "height": request.height,
            "scale": request.scale,
            "include_image": bool(request.include_image),
        },
        error_prefix="区域截图失败",
        lock=None,  # 只读
    )
    data = {
        "format": result["format"],
        "width": result["width"],
        "height": result["height"],
        "path": result["path"],
        "bytes": result["bytes"],
        "sha256_8": result["sha256_8"],
        "capture_method": result.get("capture_method", "screen_region"),
    }
    if request.include_image:
        data["image"] = result["image"]
    return ok(data=data, trace_id=None)


@app.post("/ui/dom/read", dependencies=[Security(verify_api_key)])
async def read_ui_dom(
    request: UIDOMReadRequest,
    response: Response,
):
    """读取目标窗口 Desktop DOM（UIA 主读取）。"""
    options = UIReadOptions(
        max_depth=request.max_depth,
        include_offscreen=request.include_offscreen,
        include_disabled=request.include_disabled,
        include_invisible=request.include_invisible,
        include_semantic=request.include_semantic,
        semantic_include_text_labels=request.semantic_include_text_labels,
    )
    result = await api_action(
        endpoint="/ui/dom/read",
        action=lambda: ui_read_ctrl.read_dom(window_title=request.window_title, window_hwnd=request.window_hwnd, options=options),
        payload={
            "window_title": request.window_title,
            "window_hwnd": request.window_hwnd,
            "max_depth": request.max_depth,
            "include_offscreen": request.include_offscreen,
            "include_disabled": request.include_disabled,
            "include_invisible": request.include_invisible,
            "include_semantic": request.include_semantic,
            "semantic_include_text_labels": request.semantic_include_text_labels,
        },
        error_prefix="读取 UI DOM 失败",
        lock=None,  # 只读
    )
    if result.partial:
        response.status_code = 206
    return ok(data=result.payload.model_dump(), trace_id=None)


@app.post("/ui/widgets/read", dependencies=[Security(verify_api_key)], include_in_schema=False)
async def read_ui_widgets(
    request: UIWidgetsReadRequest,
    response: Response,
):
    """读取目标窗口 Widgets（Raw DOM -> Widget Collapse -> widgets[]）。"""
    options = UIReadOptions(
        max_depth=request.max_depth,
        include_offscreen=request.include_offscreen,
        include_disabled=request.include_disabled,
        include_invisible=request.include_invisible,
        include_semantic=False,
    )
    result = await api_action(
        endpoint="/ui/widgets/read",
        action=lambda: ui_read_ctrl.read_dom(window_title=request.window_title, window_hwnd=request.window_hwnd, options=options),
        payload={
            "window_title": request.window_title,
            "window_hwnd": request.window_hwnd,
            "max_depth": request.max_depth,
            "include_offscreen": request.include_offscreen,
            "include_disabled": request.include_disabled,
            "include_invisible": request.include_invisible,
            "include_text_widgets": request.include_text_widgets,
            "collapse_icons": request.collapse_icons,
        },
        error_prefix="读取 widgets 失败",
        lock=None,  # 只读
    )

    widgets = build_widgets(
        result.payload.dom,
        window=result.payload.window,
        include_text_widgets=request.include_text_widgets,
        collapse_icons=request.collapse_icons,
    )

    actionable_widgets = sum(1 for w in widgets if w.role in ACTIONABLE_WIDGET_ROLES)
    stats = WidgetStats(
        all_elements=len(result.payload.dom.by_id or {}),
        widgets=len(widgets),
        actionable_widgets=actionable_widgets,
    )

    if result.partial:
        response.status_code = 206

    return ok(data=WidgetResponse(window=result.payload.window, stats=stats, widgets=widgets).model_dump(), trace_id=None)


@app.post("/ui/widgets/query", dependencies=[Security(verify_api_key)], include_in_schema=False)
async def query_ui_widgets(
    request: UIWidgetsQueryRequest,
    response: Response,
):
    """查询 Widgets（服务端构建 widgets v1.1 后过滤 + 裁剪返回）。"""
    options = UIReadOptions(
        max_depth=request.max_depth,
        include_offscreen=request.include_offscreen,
        include_disabled=request.include_disabled,
        include_invisible=request.include_invisible,
        include_semantic=False,
    )

    filters = to_engine_filters(request.filters)

    result = await api_action(
        endpoint="/ui/widgets/query",
        action=lambda: widget_query_ctrl.query_widgets(
            window_title=request.window_title,
            window_hwnd=request.window_hwnd,
            options=options,
            filters=filters,
            include_text_widgets=request.include_text_widgets,
            collapse_icons=request.collapse_icons,
            limit=request.limit,
            select=request.select,
        ),
        payload={
            "window_title": request.window_title,
            "window_hwnd": request.window_hwnd,
            "max_depth": request.max_depth,
            "filters": request.filters.model_dump(),
            "limit": request.limit,
            "select": request.select,
        },
        error_prefix="查询 widgets 失败",
        lock=None,  # 只读
    )

    if result.partial:
        response.status_code = 206
    return ok(
        data={
            "schema_version": "desktop_widgets_query.v2",
            "window": result.window,
            "stats": result.stats,
            "widgets": result.widgets,
        },
        trace_id=None,
    )


@app.post("/ui/widgets/click", dependencies=[Security(verify_api_key)], include_in_schema=False)
async def click_ui_widget(request: UIWidgetClickRequest, http_request: Request):
    """按 widget id 执行 click（优先 UIA Invoke，必要时退化鼠标点击）。"""
    mode = (http_request.headers.get("X-Desktop-Control-Mode") or "safe").strip().lower()
    if mode not in {"safe", "live"}:
        raise HTTPException(status_code=400, detail="X-Desktop-Control-Mode 必须是 safe 或 live")
    options = UIReadOptions(
        max_depth=request.max_depth,
        include_offscreen=False,
        include_disabled=True,
        include_invisible=False,
        include_semantic=False,
    )
    if mode == "safe":
        # 只做重定位与返回模拟计划，不执行真实动作
        widget, window, resolved_ok, resolved_by, candidates = widget_action_ctrl._resolve_widget(  # type: ignore[attr-defined]
            window_title=request.window_title,
            window_hwnd=int(request.target_hwnd) if request.target_hwnd is not None else None,
            options=options,
            widget_id=request.id,
            fingerprint=request.fingerprint,  # type: ignore[arg-type]
        )
        if widget is None:
            raise ApiError(
                status_code=404,
                code="widget_not_found",
                message=f"未找到 widget：{request.id}",
                details={"resolved_by": resolved_by, "candidates": candidates},
            )
        cx = int(widget.bounds.x + widget.bounds.width / 2)
        cy = int(widget.bounds.y + widget.bounds.height / 2)
        return ok(
            data={
                "mode": "safe",
                "simulation": {
                    "action": "click",
                    "widget_id": widget.id,
                    "resolved_by": resolved_by,
                    "center": [cx, cy],
                    "patterns": widget.patterns,
                    "target_hwnd": int(request.target_hwnd) if request.target_hwnd is not None else None,
                },
                "window": window,
            },
            trace_id=None,
        )
    trace_id = new_trace_id()
    http_request.state.trace_id = trace_id
    t0 = time.perf_counter()
    actor = (http_request.headers.get("X-Actor") or "").strip() or None
    api_key = (http_request.headers.get("X-API-Key") or "").strip()
    api_key_sha256_8 = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8] if api_key else None
    try:
        window_title_for_read = None if request.target_hwnd is not None else request.window_title

        def _action():
            if request.target_hwnd is not None:
                focused, ferr = windows_ctrl.focus_by_hwnd(int(request.target_hwnd))
                if not focused:
                    if ferr == "focus_failed":
                        raise ApiError(
                            status_code=409,
                            code="window_focus_failed",
                            message=f"窗口存在但无法激活或置前：hwnd={request.target_hwnd}",
                        )
                    raise HTTPException(status_code=404, detail=f"未找到窗口：hwnd={request.target_hwnd}")
            return widget_action_ctrl.click(
                window_title=window_title_for_read,
                options=options,
                widget_id=request.id,
                fingerprint=request.fingerprint,  # type: ignore[arg-type]
            )

        result = await api_action(
            endpoint="/ui/widgets/click",
            action=_action,
            payload={
                "id": request.id,
                "window_title": request.window_title,
                "target_hwnd": int(request.target_hwnd) if request.target_hwnd is not None else None,
                "max_depth": request.max_depth,
            },
            error_prefix="widget click 失败",
            lock=action_lock,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        append_trace_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "endpoint": "/ui/widgets/click",
                "mode": "live",
                "actor": actor,
                "api_key_sha256_8": api_key_sha256_8,
                "hwnd": int(request.target_hwnd) if request.target_hwnd is not None else int((getattr(result, "window", None) or {}).get("hwnd", 0) or 0),
                "stable_id": request.id,
                "resolved": bool(getattr(result, "resolved", True)),
                "resolved_by": getattr(result, "resolved_by", None),
                "verified": getattr(result, "verified", None),
                "verify_reason": getattr(result, "verify_reason", None),
                "duration_ms": duration_ms,
                "success": True,
                "error_code": None,
            }
        )
        return ok(data=result.__dict__, trace_id=trace_id)  # type: ignore[misc]
    except ApiError as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        append_trace_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "endpoint": "/ui/widgets/click",
                "mode": "live",
                "actor": actor,
                "api_key_sha256_8": api_key_sha256_8,
                "hwnd": int(request.target_hwnd) if request.target_hwnd is not None else 0,
                "stable_id": request.id,
                "resolved": False,
                "resolved_by": (exc.details or {}).get("resolved_by") if isinstance(exc.details, dict) else None,
                "verified": None,
                "verify_reason": None,
                "duration_ms": duration_ms,
                "success": False,
                "error_code": exc.code,
            }
        )
        raise
    except HTTPException as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        append_trace_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "endpoint": "/ui/widgets/click",
                "mode": "live",
                "actor": actor,
                "api_key_sha256_8": api_key_sha256_8,
                "hwnd": int(request.target_hwnd) if request.target_hwnd is not None else 0,
                "stable_id": request.id,
                "resolved": False,
                "resolved_by": None,
                "verified": None,
                "verify_reason": None,
                "duration_ms": duration_ms,
                "success": False,
                "error_code": "http_error",
            }
        )
        raise


@app.post("/ui/widgets/set_value", dependencies=[Security(verify_api_key)], include_in_schema=False)
async def set_value_ui_widget(request: UIWidgetSetValueRequest, http_request: Request):
    """按 widget id 设置输入值（优先 UIA ValuePattern，必要时退化键盘输入）。"""
    mode = (http_request.headers.get("X-Desktop-Control-Mode") or "safe").strip().lower()
    if mode not in {"safe", "live"}:
        raise HTTPException(status_code=400, detail="X-Desktop-Control-Mode 必须是 safe 或 live")
    options = UIReadOptions(
        max_depth=request.max_depth,
        include_offscreen=False,
        include_disabled=True,
        include_invisible=False,
        include_semantic=False,
    )
    if mode == "safe":
        widget, window, resolved_ok, resolved_by, candidates = widget_action_ctrl._resolve_widget(  # type: ignore[attr-defined]
            window_title=request.window_title,
            window_hwnd=int(request.target_hwnd) if request.target_hwnd is not None else None,
            options=options,
            widget_id=request.id,
            fingerprint=request.fingerprint,  # type: ignore[arg-type]
        )
        if widget is None:
            raise ApiError(
                status_code=404,
                code="widget_not_found",
                message=f"未找到 widget：{request.id}",
                details={"resolved_by": resolved_by, "candidates": candidates},
            )
        cx = int(widget.bounds.x + widget.bounds.width / 2)
        cy = int(widget.bounds.y + widget.bounds.height / 2)
        return ok(
            data={
                "mode": "safe",
                "simulation": {
                    "action": "set_value",
                    "widget_id": widget.id,
                    "resolved_by": resolved_by,
                    "center": [cx, cy],
                    "patterns": widget.patterns,
                    "value_len": len(request.value or ""),
                    "verify": bool(request.verify),
                    "target_hwnd": int(request.target_hwnd) if request.target_hwnd is not None else None,
                },
                "window": window,
            },
            trace_id=None,
        )
    trace_id = new_trace_id()
    http_request.state.trace_id = trace_id
    t0 = time.perf_counter()
    actor = (http_request.headers.get("X-Actor") or "").strip() or None
    api_key = (http_request.headers.get("X-API-Key") or "").strip()
    api_key_sha256_8 = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8] if api_key else None
    try:
        window_title_for_read = None if request.target_hwnd is not None else request.window_title

        def _action():
            if request.target_hwnd is not None:
                focused, ferr = windows_ctrl.focus_by_hwnd(int(request.target_hwnd))
                if not focused:
                    if ferr == "focus_failed":
                        raise ApiError(
                            status_code=409,
                            code="window_focus_failed",
                            message=f"窗口存在但无法激活或置前：hwnd={request.target_hwnd}",
                        )
                    raise HTTPException(status_code=404, detail=f"未找到窗口：hwnd={request.target_hwnd}")
            return widget_action_ctrl.set_value(
                window_title=window_title_for_read,
                options=options,
                widget_id=request.id,
                value=request.value,
                fingerprint=request.fingerprint,  # type: ignore[arg-type]
                verify=bool(request.verify),
            )

        result = await api_action(
            endpoint="/ui/widgets/set_value",
            action=_action,
            payload={
                "id": request.id,
                "window_title": request.window_title,
                "target_hwnd": int(request.target_hwnd) if request.target_hwnd is not None else None,
                "max_depth": request.max_depth,
                "verify": bool(request.verify),
                "value_len": len(request.value or ""),
            },
            error_prefix="widget set_value 失败",
            lock=action_lock,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        append_trace_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "endpoint": "/ui/widgets/set_value",
                "mode": "live",
                "actor": actor,
                "api_key_sha256_8": api_key_sha256_8,
                "hwnd": int(request.target_hwnd) if request.target_hwnd is not None else int((getattr(result, "window", None) or {}).get("hwnd", 0) or 0),
                "stable_id": request.id,
                "resolved": bool(getattr(result, "resolved", True)),
                "resolved_by": getattr(result, "resolved_by", None),
                "verified": getattr(result, "verified", None),
                "verify_reason": getattr(result, "verify_reason", None),
                "duration_ms": duration_ms,
                "success": True,
                "error_code": None,
            }
        )
        return ok(data=result.__dict__, trace_id=trace_id)  # type: ignore[misc]
    except ApiError as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        append_trace_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "endpoint": "/ui/widgets/set_value",
                "mode": "live",
                "actor": actor,
                "api_key_sha256_8": api_key_sha256_8,
                "hwnd": int(request.target_hwnd) if request.target_hwnd is not None else 0,
                "stable_id": request.id,
                "resolved": False,
                "resolved_by": (exc.details or {}).get("resolved_by") if isinstance(exc.details, dict) else None,
                "verified": None,
                "verify_reason": None,
                "duration_ms": duration_ms,
                "success": False,
                "error_code": exc.code,
            }
        )
        raise
    except HTTPException:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        append_trace_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "endpoint": "/ui/widgets/set_value",
                "mode": "live",
                "actor": actor,
                "api_key_sha256_8": api_key_sha256_8,
                "hwnd": int(request.target_hwnd) if request.target_hwnd is not None else 0,
                "stable_id": request.id,
                "resolved": False,
                "resolved_by": None,
                "verified": None,
                "verify_reason": None,
                "duration_ms": duration_ms,
                "success": False,
                "error_code": "http_error",
            }
        )
        raise


@app.post("/widgets/read", dependencies=[Security(verify_api_key)])
async def widgets_read_alias(request: UIWidgetsReadRequest, response: Response):
    """与 POST /ui/widgets/read 等价（v2 正式路径）。"""
    return await read_ui_widgets(request, response)


@app.post("/widgets/query", dependencies=[Security(verify_api_key)])
async def widgets_query_alias(request: UIWidgetsQueryRequest, response: Response):
    """与 POST /ui/widgets/query 等价（v2 正式路径）。"""
    return await query_ui_widgets(request, response)


@app.post("/widgets/act", dependencies=[Security(verify_api_key)])
async def widgets_act(body: WidgetActRequest, http_request: Request):
    """统一控件操作入口（click / set_value）。"""
    if body.action == "click":
        return await click_ui_widget(
            UIWidgetClickRequest(
                id=body.id,
                window_title=body.window_title,
                max_depth=body.max_depth,
                fingerprint=body.fingerprint,
                target_hwnd=body.target_hwnd,
            ),
            http_request,
        )
    return await set_value_ui_widget(
        UIWidgetSetValueRequest(
            id=body.id,
            value=body.value or "",
            verify=body.verify,
            window_title=body.window_title,
            max_depth=body.max_depth,
            fingerprint=body.fingerprint,
            target_hwnd=body.target_hwnd,
        ),
        http_request,
    )


# ============== 主程序 ==============

if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════╗
    ║     Desktop Control API Server           ║
    ║     为 AI 代理提供的桌面自动化服务              ║
    ╚══════════════════════════════════════════╝
    
    📍 服务地址：http://{settings.host}:{settings.port}
    📖 API 文档：http://{settings.host}:{settings.port}/docs
    🔐 API Key: 已配置 {len(VALID_API_KEYS)} 个
    
    ⚠️  注意：此服务可控制您的电脑，请确保在安全环境中运行！
    
    按 Ctrl+C 停止服务
    """)
    
    uvicorn.run(app, host=settings.host, port=settings.port)
