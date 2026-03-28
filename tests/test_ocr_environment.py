"""
本机 OCR 环境自检：pytesseract 可导入 + tesseract 可执行文件可用 + 能识别简单合成图。

未安装 Tesseract 或未加入 PATH 时跳过（不导致整仓 pytest 失败）。
"""

from __future__ import annotations

import pytest

pytest.importorskip("cv2")
pytest.importorskip("numpy")
pytest.importorskip("pytesseract")

import cv2
import numpy as np
import pytesseract


def _skip_if_no_tesseract() -> None:
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover
        pytest.skip(f"tesseract 可执行文件不可用: {exc}")


def test_tesseract_binary_on_path() -> None:
    """确认 pytesseract 能找到本机 tesseract。"""
    _skip_if_no_tesseract()
    ver = pytesseract.get_tesseract_version()
    assert ver is not None


def test_image_to_string_synthetic_word() -> None:
    """白底黑字单段英文，PSM 7 单行；验证 OCR 链路可用。"""
    _skip_if_no_tesseract()

    img = np.full((140, 520, 3), 255, dtype=np.uint8)
    cv2.putText(
        img,
        "DCAPI_OCR",
        (24, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.8,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )

    raw = pytesseract.image_to_string(img, config="--psm 7")
    normalized = "".join(ch for ch in raw.upper() if ch.isalnum() or ch == "_")
    assert "DCAPI" in normalized and "OCR" in normalized


def test_image_to_data_returns_boxes() -> None:
    """与 /locate/text 相同的 image_to_data 路径能跑通并产出框。"""
    _skip_if_no_tesseract()

    img = np.full((120, 360, 3), 255, dtype=np.uint8)
    cv2.putText(
        img,
        "BOX",
        (40, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.2,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    texts = [t.strip() for t in data["text"] if t and str(t).strip()]
    joined = " ".join(texts).upper()
    assert "BOX" in joined.replace(" ", "")
