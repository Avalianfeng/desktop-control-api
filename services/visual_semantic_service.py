from __future__ import annotations

from typing import Any, Dict, Optional

from models.ocr import OCRReadResult, WidgetOCRResponse, WidgetOCRSummary
from services.ocr_service import OCRService
from services.widget_cropper import WidgetCropper


class VisualSemanticService:
    """控件裁剪 + OCR 组合。"""

    def __init__(self, cropper: WidgetCropper, ocr: OCRService) -> None:
        self._cropper = cropper
        self._ocr = ocr

    def read_widget(
        self,
        *,
        widget_id: str,
        window_title: Optional[str],
        target_hwnd: Optional[int],
        fingerprint: Optional[dict],
        max_depth: int,
        lang: str,
        tesseract_config: Optional[str],
        include_text_widgets: bool = True,
        collapse_icons: bool = True,
        scale: float = 1.0,
        crop_padding_px: int = 0,
    ) -> Dict[str, Any]:
        cap = self._cropper.capture_widget(
            widget_id=widget_id,
            window_title=window_title,
            target_hwnd=target_hwnd,
            fingerprint=fingerprint,
            max_depth=max_depth,
            include_text_widgets=include_text_widgets,
            collapse_icons=collapse_icons,
            scale=scale,
            crop_padding_px=crop_padding_px,
        )
        ocr_result = self._ocr.read_image(
            cap["image_path"],
            lang=lang,
            tesseract_config=tesseract_config,
        )
        wsum = cap["widget"]
        raw_t = wsum.get("text")
        if isinstance(raw_t, dict):
            text_flat = (raw_t.get("value") or "") or ""
        else:
            text_flat = (raw_t or "") or ""
        if not text_flat:
            text_flat = (wsum.get("text_legacy") or "") or ""
        body = WidgetOCRResponse(
            widget=WidgetOCRSummary(
                id=wsum["id"],
                text=text_flat,
                role=wsum.get("role"),
                normalized=wsum.get("normalized"),
            ),
            image_path=cap["image_path"],
            ocr=ocr_result,
        )
        out = body.model_dump()
        # 兼容约定：ocr.text 与 full_text 同义
        ocr_block = out.get("ocr") or {}
        ocr_block["text"] = ocr_block.get("full_text") or ""
        out["ocr"] = ocr_block
        out["resolved_by"] = cap.get("resolved_by")
        out["resolved_ok"] = cap.get("resolved_ok")
        out["capture_method"] = cap.get("capture_method")
        out["image_width"] = cap.get("image_width")
        out["image_height"] = cap.get("image_height")
        out["capture_bounds"] = cap.get("capture_bounds")
        out["crop_padding_px"] = cap.get("crop_padding_px")
        return out
