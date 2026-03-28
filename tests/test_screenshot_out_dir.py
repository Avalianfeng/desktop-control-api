from __future__ import annotations

from pathlib import Path

from controllers.screenshot import ScreenshotController


def test_default_screenshot_dir_under_updates_screenshots(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    c = ScreenshotController()
    d = c._default_screenshot_dir()
    norm = Path(d).resolve()
    assert norm.is_absolute()
    parts = {p.lower() for p in norm.parts}
    assert "updates" in parts
    assert "screenshots" in parts


def test_capture_to_file_uses_fixed_dir_and_absolute_path(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "updates" / "screenshots").mkdir(parents=True)

    c = ScreenshotController()
    monkeypatch.setattr(
        c,
        "capture",
        lambda region=None: {
            "base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            "width": 1,
            "height": 1,
        },
    )

    meta = c.capture_to_file(region=None)
    p = meta["path"]
    assert p
    assert Path(p).is_absolute()
    assert "updates/screenshots" in p.replace("\\", "/")
