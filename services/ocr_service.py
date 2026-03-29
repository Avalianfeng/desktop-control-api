from __future__ import annotations

from pathlib import Path
from typing import Optional

from errors import ApiError
from models.ocr import OCRLine, OCRReadResult


class OCRService:
    """Tesseract OCR 封装（显式 lang/config，供 HTTP 与组合服务复用）。"""

    def read_image(
        self,
        path: str | Path,
        *,
        lang: str = "eng",
        tesseract_config: Optional[str] = None,
    ) -> OCRReadResult:
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:  # pragma: no cover
            raise ApiError(
                status_code=500,
                code="pytesseract_missing",
                message="未安装 pytesseract",
                cause=exc,
            ) from exc

        p = Path(path)
        kw: dict = {"lang": lang or "eng", "output_type": Output.DICT}
        if tesseract_config:
            kw["config"] = tesseract_config

        try:
            data = pytesseract.image_to_data(str(p), **kw)
        except pytesseract.TesseractNotFoundError as exc:  # type: ignore[attr-defined]
            raise ApiError(
                status_code=503,
                code="tesseract_not_found",
                message="未找到 Tesseract 可执行文件，请安装并加入 PATH",
                cause=exc,
            ) from exc
        except Exception as exc:
            raise ApiError(
                status_code=500,
                code="ocr_failed",
                message="OCR 执行失败",
                cause=exc,
                details={"path": str(p)},
            ) from exc

        lines: list[OCRLine] = []
        texts: list[str] = []
        n = len(data.get("text", []))
        for i in range(n):
            txt = str(data["text"][i] or "").strip()
            if not txt:
                continue
            conf_raw = int(data["conf"][i]) if i < len(data["conf"]) else -1
            conf: Optional[float]
            if conf_raw < 0:
                conf = None
            else:
                conf = max(0.0, min(1.0, float(conf_raw) / 100.0))
            left = int(data["left"][i]) if i < len(data["left"]) else 0
            top = int(data["top"][i]) if i < len(data["top"]) else 0
            w = int(data["width"][i]) if i < len(data["width"]) else 0
            h = int(data["height"][i]) if i < len(data["height"]) else 0
            lines.append(OCRLine(text=txt, bbox=[left, top, w, h], conf=conf))
            texts.append(txt)

        full_text = " ".join(texts)
        return OCRReadResult(lines=lines, full_text=full_text)
