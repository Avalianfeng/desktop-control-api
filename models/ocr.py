from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class OCRLine(BaseModel):
    """单行 OCR 结果（坐标相对输入图像左上角）。"""

    text: str
    bbox: List[int] = Field(..., min_length=4, max_length=4, description="[x, y, width, height]")
    conf: Optional[float] = Field(default=None, description="置信度 0~1；无效时为 null（如 Tesseract -1）")


class OCRReadResult(BaseModel):
    """全图 OCR：词/块级列表。"""

    lines: List[OCRLine] = Field(default_factory=list)
    full_text: str = Field(default="", description="按行顺序拼接的纯文本")


class WidgetOCRSummary(BaseModel):
    """read_widget 响应中的 widget 摘要。"""

    id: str
    text: str = Field(default="", description="UIA 侧文本/标签（与 widgets.read 一致）")
    role: Optional[str] = None
    normalized: Optional[str] = None


class WidgetOCRResponse(BaseModel):
    """POST /ocr/read_widget 的 data 负载。"""

    widget: WidgetOCRSummary
    image_path: str
    ocr: OCRReadResult
