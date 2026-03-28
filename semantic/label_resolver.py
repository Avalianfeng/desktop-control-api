from __future__ import annotations

from typing import Iterable, Optional

from models.ui_dom import UIElement


# 最小映射：先覆盖你提到的示例；后续按实际采样扩展
ICON_MAP: dict[str, str] = {
    "\uf754": "memory_clear",
}


def normalize_icon(text: str, *, enabled: bool = True) -> str:
    if not enabled:
        return text
    if not text:
        return text
    return ICON_MAP.get(text, text)


def _nonempty_text(nodes: Iterable[UIElement]) -> list[str]:
    out: list[str] = []
    for n in nodes:
        t = (n.text or "").strip() or (n.name or "").strip()
        if t:
            out.append(t)
    return out


def extract_label(node: UIElement) -> str:
    """按钮/输入框的 label 提取：优先自身 text/name，其次直接子 text。"""
    self_text = (node.text or "").strip() or (node.name or "").strip()
    if self_text:
        return self_text

    # 规则 1：button -> child text
    if node.type == "button" and node.children:
        texts = _nonempty_text([c for c in node.children if c.type == "text"])
        if texts:
            return texts[0]

        # 轻量“容器穿透”：button -> container -> text
        for c in node.children:
            if c.type not in {"container", "group", "custom", "pane"}:
                continue
            texts = _nonempty_text([gc for gc in c.children if gc.type == "text"])
            if texts:
                return texts[0]

    return ""


def deepest_text(node: UIElement) -> str:
    """文本折叠：沿子树取最深处的非空 text/name（DFS，优先更深）。"""
    best: Optional[str] = None

    def _dfs(n: UIElement) -> None:
        nonlocal best
        for c in n.children:
            _dfs(c)
        t = (n.text or "").strip() or (n.name or "").strip()
        if t and best is None:
            best = t

    _dfs(node)
    return best or ""

