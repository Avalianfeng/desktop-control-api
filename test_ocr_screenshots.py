"""
从 ``updates/screenshots``（可配置）选取 PNG，用本机 Tesseract 做真实 OCR 自检。

不属于 pytest 默认收集范围（``pytest.ini`` 的 ``testpaths`` 仅为 ``tests``）。
无需启动 API 服务。

示例::

    python test_ocr_screenshots.py --list
    python test_ocr_screenshots.py --pick 0
    python test_ocr_screenshots.py --pick 0,1 --lang chi_sim+eng --psm 6
    python test_ocr_screenshots.py -i
    python test_ocr_screenshots.py --show-langs

中文界面若全是英文乱码：默认未指定 ``--lang`` 时 Tesseract 只用 **eng**。请安装 **chi_sim.traineddata**
（简体）到 ``tessdata``，并使用 ``--lang chi_sim+eng``；混合排版可试 ``--psm 6``。
详见官方数据文件说明：https://tesseract-ocr.github.io/tessdoc/Data-Files

若未安装 Tesseract 或未加入 PATH，脚本会报错退出。
"""

from __future__ import annotations

import env_bootstrap  # noqa: F401 — 加载 .env（如 TESSDATA_PREFIX）

import argparse
import os
import sys
from pathlib import Path
from typing import List

import cv2


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def discover_pngs(screens_dir: Path) -> List[Path]:
    """按修改时间从新到旧排序。"""
    if not screens_dir.is_dir():
        return []
    found = list(screens_dir.rglob("*.png"))
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found


def parse_pick(s: str, n: int) -> List[int]:
    out: List[int] = []
    for part in s.replace(" ", "").split(","):
        if not part:
            continue
        i = int(part, 10)
        if i < 0 or i >= n:
            raise ValueError(f"序号越界: {i}（有效 0..{n - 1}）")
        out.append(i)
    if not out:
        raise ValueError("未指定有效序号")
    return out


def print_tesseract_lang_diagnostic() -> None:
    """打印已安装语言包与环境变量，便于排查中文无法识别。"""
    import pytesseract

    ver = pytesseract.get_tesseract_version()
    langs = sorted(pytesseract.get_languages())
    print(f"tesseract version: {ver}")
    print(f"TESSDATA_PREFIX: {os.environ.get('TESSDATA_PREFIX') or '(未设置)'}")
    print(f"pytesseract.tesseract_cmd: {getattr(pytesseract.pytesseract, 'tesseract_cmd', '(默认)')}")
    print(f"已安装语言 ({len(langs)}): {', '.join(langs)}")
    if "chi_sim" not in langs and "chi_tra" not in langs:
        print(
            "\n提示: 列表中无 chi_sim（简体）时，中文会被当成英文硬认，出现乱码。\n"
            "请从 https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata\n"
            "下载后放入安装目录下的 tessdata（例如 C:\\Program Files\\Tesseract-OCR\\tessdata），\n"
            "再运行安装程序追加语言，或手动复制该文件后重试 --show-langs。",
            file=sys.stderr,
        )


def run_ocr(path: Path, *, lang: str | None, psm: int, print_data: bool) -> None:
    import pytesseract

    img = cv2.imread(str(path))
    if img is None:
        print(f"[skip] 无法读取图像: {path}", file=sys.stderr)
        return

    cfg = f"--psm {psm}"
    kw: dict = {"config": cfg}
    if lang:
        kw["lang"] = lang

    text = pytesseract.image_to_string(img, **kw)
    print("--- image_to_string ---")
    print(text.rstrip() or "(空)")

    if print_data:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, **kw)
        n = len(data.get("text", []))
        nonempty = sum(1 for t in data.get("text", []) if (t or "").strip())
        print(f"\n--- image_to_data --- boxes(non-empty text)={nonempty} / {n}")
        for i in range(n):
            t = (data["text"][i] or "").strip()
            if not t:
                continue
            conf = data["conf"][i]
            left, top, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            print(f"  [{i}] conf={conf!r} bbox=({left},{top},{w}x{h}) text={t!r}")


def main() -> None:
    root = _repo_root()
    default_dir = root / "updates" / "screenshots"

    parser = argparse.ArgumentParser(description="对 updates/screenshots 下 PNG 做 Tesseract OCR")
    parser.add_argument(
        "--dir",
        type=Path,
        default=default_dir,
        help=f"扫描目录（默认: {default_dir}）",
    )
    parser.add_argument("--list", action="store_true", help="仅列出候选 PNG，不识别")
    parser.add_argument("--pick", type=str, metavar="INDICES", help="逗号分隔序号，0 为最新修改的文件")
    parser.add_argument("-i", "--interactive", action="store_true", help="打印列表后在终端询问序号")
    parser.add_argument("--lang", type=str, default=None, help="Tesseract -l，如 chi_sim+eng")
    parser.add_argument("--psm", type=int, default=3, help="Tesseract --psm（默认 3 全自动页）")
    parser.add_argument("--data", action="store_true", help="额外输出 image_to_data 非空框")
    parser.add_argument(
        "--show-langs",
        action="store_true",
        help="列出本机 Tesseract 已安装语言与 tessdata 相关环境（不识别图片）",
    )
    args = parser.parse_args()

    if args.show_langs:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
        except ImportError:
            print("缺少 pytesseract：pip install pytesseract", file=sys.stderr)
            sys.exit(2)
        except pytesseract.TesseractNotFoundError as e:  # type: ignore[attr-defined]
            print(f"未找到 tesseract 可执行文件: {e}", file=sys.stderr)
            sys.exit(2)
        print_tesseract_lang_diagnostic()
        return

    screens = args.dir.resolve()
    pngs = discover_pngs(screens)
    if not pngs:
        print(f"未找到 PNG: {screens}（含子目录）", file=sys.stderr)
        sys.exit(1)

    if args.list:
        for i, p in enumerate(pngs):
            rel = p.relative_to(root) if p.is_relative_to(root) else p
            print(f"[{i}] {rel}")
        return

    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except ImportError:
        print("缺少 pytesseract：pip install pytesseract", file=sys.stderr)
        sys.exit(2)
    except pytesseract.TesseractNotFoundError as e:  # type: ignore[attr-defined]
        print(f"未找到 tesseract 可执行文件（请安装并加入 PATH）: {e}", file=sys.stderr)
        sys.exit(2)

    indices: List[int]
    if args.pick is not None:
        try:
            indices = parse_pick(args.pick, len(pngs))
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
    elif args.interactive or sys.stdin.isatty():
        for i, p in enumerate(pngs[:50]):
            rel = p.relative_to(root) if p.is_relative_to(root) else p
            print(f"[{i}] {rel}")
        if len(pngs) > 50:
            print(f"... 另有 {len(pngs) - 50} 个文件未显示（请用 --pick 或缩小 --dir）")
        try:
            raw = input("输入要识别的序号（逗号分隔，默认 0）: ").strip()
        except EOFError:
            print("无 stdin，请使用 --pick", file=sys.stderr)
            sys.exit(1)
        raw = raw or "0"
        try:
            indices = parse_pick(raw, len(pngs))
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
    else:
        print("非交互环境请指定 --pick，例如: --pick 0", file=sys.stderr)
        sys.exit(1)

    seen: set[int] = set()
    for idx in indices:
        if idx in seen:
            continue
        seen.add(idx)
        path = pngs[idx]
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"\n======== file [{idx}] {rel} ========")
        run_ocr(path, lang=args.lang, psm=args.psm, print_data=args.data)


if __name__ == "__main__":
    main()
