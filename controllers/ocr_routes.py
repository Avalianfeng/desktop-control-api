from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Security
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from deps import Deps
from response_envelope import ok
from services.allowed_paths import resolve_ocr_image_path
from settings import default_ui_max_depth


class OCRReadRequest(BaseModel):
    image_path: str = Field(..., description="工作目录下的图像路径（相对或绝对）")
    lang: str = Field(default="eng", min_length=1, max_length=64)
    tesseract_config: Optional[str] = Field(default=None, max_length=500, description="如 --psm 6")


class WidgetScreenshotRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=200, description="widget 稳定 id")
    window_title: Optional[str] = Field(default=None, description="窗口标题（可选；与 target_hwnd 二选一逻辑同 click）")
    max_depth: int = Field(default_factory=default_ui_max_depth, ge=1, le=30)
    fingerprint: Optional[Dict[str, Any]] = Field(default=None)
    target_hwnd: Optional[int] = Field(default=None, ge=1)
    scale: float = Field(default=1.0, gt=0, le=4.0)
    crop_padding_px: int = Field(
        default=4,
        ge=0,
        le=64,
        description="裁剪前在 UIA 矩形四周各扩展的像素（缓解贴边 OCR 切字）；Windows 上会夹到客户区内",
    )
    include_text_widgets: bool = True
    collapse_icons: bool = True


class WidgetOCRRequest(WidgetScreenshotRequest):
    lang: str = Field(default="eng", min_length=1, max_length=64)
    tesseract_config: Optional[str] = Field(default=None, max_length=500)


class VisionFindTextRequest(BaseModel):
    """与 POST /locate/text 请求体一致（正式视觉命名空间）。"""

    text: str = Field(..., description="要查找的文字")
    screen_region: Optional[List[int]] = Field(default=None, description="搜索区域 [x, y, width, height]")


class VisionMatchTemplateRequest(BaseModel):
    """与 POST /locate/image 请求体一致（正式视觉命名空间）。"""

    image_path: str = Field(..., description="要查找的图像路径")
    confidence: float = Field(default=0.8, ge=0, le=1, description="匹配置信度（0-1）")
    screen_region: Optional[List[int]] = Field(default=None, description="搜索区域 [x, y, width, height]")


class OCRReadWindowRequest(BaseModel):
    """调试/验收：对单窗内多个控件依次裁剪 OCR（勿用于生产 Agent 高频路径）。"""

    window_hwnd: int = Field(..., ge=1)
    focus_first: bool = Field(default=True, description="执行前 best-effort 聚焦该窗口")
    max_depth: int = Field(default_factory=default_ui_max_depth, ge=1, le=30)
    query_limit: int = Field(default=200, ge=1, le=500, description="widgets/query 拉取条数，再按面积截断")
    max_widgets: int = Field(default=20, ge=1, le=80, description="最多做 OCR 的控件数量")
    min_bounds_area: int = Field(default=400, ge=0, le=10_000_000)
    lang: str = Field(default="eng", min_length=1, max_length=64)
    tesseract_config: Optional[str] = Field(default=None, max_length=500)
    crop_padding_px: int = Field(default=4, ge=0, le=64, description="同 /ocr/read_widget 的 crop_padding_px")
    include_text_widgets: bool = True
    collapse_icons: bool = True


def _deprecated_json(data: Any, *, successor: str) -> JSONResponse:
    return JSONResponse(
        content={"success": True, "data": data, "error": None, "trace_id": None},
        headers={"Deprecation": "true", "Link": f'<{successor}>; rel="successor-version"'},
    )


def build_visual_router(deps: Deps) -> APIRouter:
    import server as srv

    router = APIRouter(tags=["visual"])

    @router.post("/ocr/read", dependencies=[Security(srv.verify_api_key)], include_in_schema=False)
    async def ocr_read(body: OCRReadRequest):
        def _run():
            path = resolve_ocr_image_path(body.image_path)
            result = deps.ocr_service.read_image(
                str(path),
                lang=body.lang,
                tesseract_config=body.tesseract_config,
            )
            data = result.model_dump()
            data["text"] = data.get("full_text") or ""
            return data

        out = await srv.api_action(
            endpoint="/ocr/read",
            action=_run,
            payload={
                "image_path": body.image_path,
                "lang": body.lang,
                "has_tesseract_config": body.tesseract_config is not None,
            },
            error_prefix="OCR 读取失败",
            lock=None,
        )
        return _deprecated_json(out, successor="/vision/ocr/read")

    @router.post("/screenshot/widget", dependencies=[Security(srv.verify_api_key)], include_in_schema=False)
    async def screenshot_widget(body: WidgetScreenshotRequest):
        def _run():
            return deps.widget_cropper.capture_widget(
                widget_id=body.id,
                window_title=body.window_title,
                target_hwnd=body.target_hwnd,
                fingerprint=body.fingerprint,
                max_depth=body.max_depth,
                include_text_widgets=body.include_text_widgets,
                collapse_icons=body.collapse_icons,
                scale=body.scale,
                crop_padding_px=body.crop_padding_px,
            )

        out = await srv.api_action(
            endpoint="/screenshot/widget",
            action=_run,
            payload={"id": body.id, "target_hwnd": body.target_hwnd},
            error_prefix="widget 截图失败",
            lock=None,
        )
        return _deprecated_json(out, successor="/vision/screenshot/widget")

    @router.post("/ocr/read_widget", dependencies=[Security(srv.verify_api_key)], include_in_schema=False)
    async def ocr_read_widget(body: WidgetOCRRequest):
        def _run():
            return deps.visual_semantic_service.read_widget(
                widget_id=body.id,
                window_title=body.window_title,
                target_hwnd=body.target_hwnd,
                fingerprint=body.fingerprint,
                max_depth=body.max_depth,
                lang=body.lang,
                tesseract_config=body.tesseract_config,
                include_text_widgets=body.include_text_widgets,
                collapse_icons=body.collapse_icons,
                scale=body.scale,
                crop_padding_px=body.crop_padding_px,
            )

        out = await srv.api_action(
            endpoint="/ocr/read_widget",
            action=_run,
            payload={"id": body.id, "lang": body.lang},
            error_prefix="widget OCR 失败",
            lock=None,
        )
        return _deprecated_json(out, successor="/vision/ocr/widget")

    if bool(getattr(srv.settings, "expose_debug_routes", False)):
        @router.post("/ocr/read_window", dependencies=[Security(srv.verify_api_key)], include_in_schema=False)
        async def ocr_read_window(body: OCRReadWindowRequest):
            def _run():
                from errors import ApiError
                from models.ui_dom import UIReadOptions
                from query.widget_query_engine import WidgetQueryFilters

                if body.focus_first:
                    deps.windows_ctrl.focus_by_hwnd(int(body.window_hwnd))

                options = UIReadOptions(
                    max_depth=body.max_depth,
                    include_offscreen=False,
                    include_disabled=True,
                    include_invisible=False,
                    include_semantic=False,
                )
                q = deps.widget_query_ctrl.query_widgets(
                    window_title=None,
                    window_hwnd=int(body.window_hwnd),
                    options=options,
                    filters=WidgetQueryFilters(),
                    include_text_widgets=body.include_text_widgets,
                    collapse_icons=body.collapse_icons,
                    limit=int(body.query_limit),
                    select=["id", "role", "text", "normalized", "bounds"],
                )

                rows: list[dict] = []
                for w in q.widgets:
                    if len(rows) >= int(body.max_widgets):
                        break
                    b = w.get("bounds") or {}
                    area = int(b.get("width") or 0) * int(b.get("height") or 0)
                    if area < int(body.min_bounds_area):
                        continue
                    wid = str(w.get("id") or "")
                    if not wid:
                        continue
                    try:
                        r = deps.visual_semantic_service.read_widget(
                            widget_id=wid,
                            window_title=None,
                            target_hwnd=int(body.window_hwnd),
                            fingerprint=None,
                            max_depth=body.max_depth,
                            lang=body.lang,
                            tesseract_config=body.tesseract_config,
                            include_text_widgets=body.include_text_widgets,
                            collapse_icons=body.collapse_icons,
                            scale=1.0,
                            crop_padding_px=body.crop_padding_px,
                        )
                        wg = r.get("widget") or {}
                        oc = r.get("ocr") or {}
                        rows.append(
                            {
                                "id": wg.get("id"),
                                "role": wg.get("role"),
                                "uia_text": wg.get("text"),
                                "normalized": wg.get("normalized"),
                                "ocr_text": oc.get("text"),
                                "ocr_lines": oc.get("lines"),
                                "image_path": r.get("image_path"),
                                "image_width": r.get("image_width"),
                                "image_height": r.get("image_height"),
                            }
                        )
                    except ApiError as e:
                        rows.append(
                            {
                                "id": wid,
                                "error": {"code": e.code, "message": e.message},
                            }
                        )

                return {
                    "window": q.window,
                    "partial": q.partial,
                    "widgets": rows,
                    "stats": {"ocr_count": len(rows), "query_returned": len(q.widgets)},
                }

            out = await srv.api_action(
                endpoint="/ocr/read_window",
                action=_run,
                payload={"window_hwnd": body.window_hwnd, "max_widgets": body.max_widgets},
                error_prefix="窗口批量 OCR 失败",
                lock=None,
            )
            return ok(data=out, trace_id=None)

    return router


def build_vision_router(deps: Deps) -> APIRouter:
    """正式 /vision/* 命名空间（与 CORE_PRINCIPLES / AI_PROTOCOL 对齐）。"""
    import server as srv

    r = APIRouter(prefix="/vision", tags=["vision"])

    @r.post("/ocr/read", dependencies=[Security(srv.verify_api_key)])
    async def vision_ocr_read(body: OCRReadRequest):
        def _run():
            path = resolve_ocr_image_path(body.image_path)
            result = deps.ocr_service.read_image(
                str(path),
                lang=body.lang,
                tesseract_config=body.tesseract_config,
            )
            data = result.model_dump()
            data["text"] = data.get("full_text") or ""
            return data

        out = await srv.api_action(
            endpoint="/vision/ocr/read",
            action=_run,
            payload={
                "image_path": body.image_path,
                "lang": body.lang,
                "has_tesseract_config": body.tesseract_config is not None,
            },
            error_prefix="OCR 读取失败",
            lock=None,
        )
        return ok(data=out, trace_id=None)

    @r.post("/screenshot/widget", dependencies=[Security(srv.verify_api_key)])
    async def vision_screenshot_widget(body: WidgetScreenshotRequest):
        def _run():
            return deps.widget_cropper.capture_widget(
                widget_id=body.id,
                window_title=body.window_title,
                target_hwnd=body.target_hwnd,
                fingerprint=body.fingerprint,
                max_depth=body.max_depth,
                include_text_widgets=body.include_text_widgets,
                collapse_icons=body.collapse_icons,
                scale=body.scale,
                crop_padding_px=body.crop_padding_px,
            )

        out = await srv.api_action(
            endpoint="/vision/screenshot/widget",
            action=_run,
            payload={"id": body.id, "target_hwnd": body.target_hwnd},
            error_prefix="widget 截图失败",
            lock=None,
        )
        return ok(data=out, trace_id=None)

    @r.post("/ocr/widget", dependencies=[Security(srv.verify_api_key)])
    async def vision_ocr_widget(body: WidgetOCRRequest):
        def _run():
            return deps.visual_semantic_service.read_widget(
                widget_id=body.id,
                window_title=body.window_title,
                target_hwnd=body.target_hwnd,
                fingerprint=body.fingerprint,
                max_depth=body.max_depth,
                lang=body.lang,
                tesseract_config=body.tesseract_config,
                include_text_widgets=body.include_text_widgets,
                collapse_icons=body.collapse_icons,
                scale=body.scale,
                crop_padding_px=body.crop_padding_px,
            )

        out = await srv.api_action(
            endpoint="/vision/ocr/widget",
            action=_run,
            payload={"id": body.id, "lang": body.lang},
            error_prefix="widget OCR 失败",
            lock=None,
        )
        return ok(data=out, trace_id=None)

    @r.post("/widget", dependencies=[Security(srv.verify_api_key)])
    async def vision_widget_combined(body: WidgetOCRRequest):
        """裁剪控件并 OCR（与 /vision/ocr/widget 同义，强调「单端点感知」）。"""

        def _run():
            return deps.visual_semantic_service.read_widget(
                widget_id=body.id,
                window_title=body.window_title,
                target_hwnd=body.target_hwnd,
                fingerprint=body.fingerprint,
                max_depth=body.max_depth,
                lang=body.lang,
                tesseract_config=body.tesseract_config,
                include_text_widgets=body.include_text_widgets,
                collapse_icons=body.collapse_icons,
                scale=body.scale,
                crop_padding_px=body.crop_padding_px,
            )

        out = await srv.api_action(
            endpoint="/vision/widget",
            action=_run,
            payload={"id": body.id, "lang": body.lang},
            error_prefix="widget OCR 失败",
            lock=None,
        )
        return ok(data=out, trace_id=None)

    @r.post("/find_text", dependencies=[Security(srv.verify_api_key)])
    async def vision_find_text(body: VisionFindTextRequest):
        validated_region = srv.ensure_region(body.screen_region, name="screen_region")
        result = await srv.api_action(
            endpoint="/vision/find_text",
            action=lambda: deps.locator_ctrl.locate_text(body.text, region=validated_region),
            payload={"text": body.text, "screen_region": validated_region},
            error_prefix="文字定位失败",
            lock=None,
        )
        if result:
            return ok(data={"found": True, "location": result}, trace_id=None)
        return ok(data={"found": False, "message": f"未找到文字：{body.text}"}, trace_id=None)

    @r.post("/match_template", dependencies=[Security(srv.verify_api_key)])
    async def vision_match_template(body: VisionMatchTemplateRequest):
        import os

        validated_region = srv.ensure_region(body.screen_region, name="screen_region")
        if not os.path.exists(body.image_path):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"图像文件不存在：{body.image_path}")

        result = await srv.api_action(
            endpoint="/vision/match_template",
            action=lambda: deps.locator_ctrl.locate_image(
                body.image_path,
                confidence=body.confidence,
                region=validated_region,
            ),
            payload={"image_path": body.image_path, "confidence": body.confidence, "screen_region": validated_region},
            error_prefix="图像定位失败",
            lock=None,
        )
        if result:
            return ok(data={"found": True, "location": result}, trace_id=None)
        return ok(data={"found": False, "message": "未找到匹配图像"}, trace_id=None)

    return r
