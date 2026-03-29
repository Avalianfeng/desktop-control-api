from __future__ import annotations

import hashlib
from typing import List, Set

from models.ui_dom import DesktopDOMData, UIElement

from dom.filter import is_visible
from semantic.label_resolver import deepest_text, extract_label, normalize_icon
from semantic.label_normalizer import normalize_label
from semantic.role_infer import infer_role
from semantic.widget_types import Widget, WidgetText


def collapse_tree(root: UIElement, *, collapse_icons: bool = True) -> UIElement:
    """
    生成折叠后的“Widget 友好”树（不修改原树）。

    - button: label 提升（child text -> button.label），并移除子节点
    - text: 若存在子树，则折叠为 deepest_text
    - icon: 最小映射表转换
    """

    children = [collapse_tree(c, collapse_icons=collapse_icons) for c in root.children]

    text = root.text
    name = root.name

    if root.type == "button":
        label = extract_label(root)  # 用原树提取（含未折叠子 text）
        if not label:
            label = (text or "").strip() or (name or "").strip()
        if collapse_icons:
            label = normalize_icon(label)
        return root.model_copy(update={"text": label, "name": label, "children": []})

    if root.type == "text" and children:
        folded = deepest_text(root)
        if collapse_icons:
            folded = normalize_icon(folded)
        return root.model_copy(update={"text": folded, "name": folded, "children": []})

    if collapse_icons:
        nt = normalize_icon((text or "").strip())
        nn = normalize_icon((name or "").strip())
        if nt != text or nn != name:
            return root.model_copy(update={"text": nt, "name": nn, "children": children})

    if children != root.children:
        return root.model_copy(update={"children": children})
    return root


def _stable_widget_id(
    *,
    hwnd: int,
    control_type: str,
    automation_id: str | None,
    runtime_id: str | None,
    uia_path: str,
) -> tuple[str, dict]:
    """
    生成稳定 Widget.id（locator）。
    - 优先 automation_id（跨运行更可能稳定）
    - 其次 runtime_id（通常仅同一运行稳定）
    - 再退化 uia_path（结构变动会漂移）
    """
    aid = (automation_id or "").strip() or None
    rid = (runtime_id or "").strip() or None
    ct = (control_type or "").strip()

    if aid:
        key = f"hwnd={hwnd};ct={ct};aid={aid}"
        source = "automation_id"
    elif rid:
        key = f"hwnd={hwnd};ct={ct};rid={rid}"
        source = "runtime_id"
    else:
        key = f"hwnd={hwnd};ct={ct};path={uia_path}"
        source = "uia_path"

    digest12 = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"w_{digest12}", {"locator_source": source, "locator_key": key}


def _merge_widget_text(node: UIElement) -> tuple[str, str | None]:
    """
    widgets 文本合并策略（v1.2）：Name + LabeledBy + Value（按可读性拼接）。
    返回 (merged_text, value)
    """
    parts: list[str] = []
    name = ((node.text or "").strip() or (node.name or "").strip()).strip()
    labeled_by = (getattr(node, "uia_labeled_by", None) or "").strip()
    value = (getattr(node, "uia_value", None) or None)
    value_s = (value or "").strip()

    if labeled_by and labeled_by != name:
        parts.append(labeled_by)
    if name:
        parts.append(name)
    if value_s and value_s not in parts:
        parts.append(value_s)

    merged = " ".join(p for p in parts if p).strip()
    return merged, (value_s or None)


def build_widgets(
    dom: DesktopDOMData,
    *,
    window: dict | None = None,
    include_text_widgets: bool = True,
    collapse_icons: bool = True,
) -> List[Widget]:
    if not dom.root:
        return []

    collapsed_root = collapse_tree(dom.root, collapse_icons=collapse_icons)

    widget_payloads: List[dict] = []
    seen_node_ids: Set[str] = set()
    hwnd = int((window or {}).get("hwnd", 0) or 0)

    def _visit(node: UIElement, parent_widget_id: str | None) -> None:
        if node.id in seen_node_ids:
            return
        seen_node_ids.add(node.id)

        visible = is_visible(node)
        current_parent_widget_id = parent_widget_id
        if visible:
            if node.type in {"button", "input", "checkbox", "radio", "menu_item", "tab_item", "list_item", "link"}:
                # collapsed tree 已做 button label 提升与 icon 折叠：这里只取最终文本 + 额外合并 label/value
                if node.type == "button":
                    text = (node.text or "").strip() or (node.name or "").strip()
                    merged_text, value = text, None
                else:
                    merged_text, value = _merge_widget_text(node)
                    text = merged_text or (node.text or "").strip() or (node.name or "").strip()
                normalized = normalize_label(text, control_type=node.control_type)
                role = infer_role(
                    element_type=node.type,
                    control_type=node.control_type,
                    text=text,
                    normalized=normalized,
                )
                wid, locator_meta = _stable_widget_id(
                    hwnd=hwnd,
                    control_type=node.control_type,
                    automation_id=getattr(node, "uia_automation_id", None),
                    runtime_id=getattr(node, "uia_runtime_id", None),
                    uia_path=node.id,
                )
                wt = WidgetText.from_uia_merged(text)
                widget_payloads.append(
                    {
                        "id": wid,
                        "type": node.type,
                        "role": role,
                        "text": wt,
                        "text_legacy": text,
                        "normalized": normalized,
                        "bounds": node.bounds,
                        "enabled": bool(node.enabled),
                        "visible": bool(node.visible) and visible,
                        "focusable": bool(getattr(node, "focusable", False)),
                        "uia_path": node.id,
                        "parent_id": current_parent_widget_id,
                        "automation_id": getattr(node, "uia_automation_id", None),
                        "runtime_id": getattr(node, "uia_runtime_id", None),
                        "patterns": list(getattr(node, "uia_patterns", None) or []),
                        "value": value,
                        "meta": {"source_type": node.type, "control_type": node.control_type, **locator_meta},
                    }
                )
                current_parent_widget_id = wid
            elif include_text_widgets and node.type == "text":
                text = (node.text or "").strip() or (node.name or "").strip()
                if text:
                    normalized = normalize_label(text, control_type=node.control_type)
                    role = infer_role(
                        element_type=node.type,
                        control_type=node.control_type,
                        text=text,
                        normalized=normalized,
                    )
                    wid, locator_meta = _stable_widget_id(
                        hwnd=hwnd,
                        control_type=node.control_type,
                        automation_id=getattr(node, "uia_automation_id", None),
                        runtime_id=getattr(node, "uia_runtime_id", None),
                        uia_path=node.id,
                    )
                    wt = WidgetText.from_uia_merged(text)
                    widget_payloads.append(
                        {
                            "id": wid,
                            "type": node.type,
                            "role": role,
                            "text": wt,
                            "text_legacy": text,
                            "normalized": normalized,
                            "bounds": node.bounds,
                            "enabled": bool(node.enabled),
                            "visible": bool(node.visible) and visible,
                            "focusable": bool(getattr(node, "focusable", False)),
                            "uia_path": node.id,
                            "parent_id": current_parent_widget_id,
                            "automation_id": getattr(node, "uia_automation_id", None),
                            "runtime_id": getattr(node, "uia_runtime_id", None),
                            "patterns": list(getattr(node, "uia_patterns", None) or []),
                            "value": None,
                            "meta": {"source_type": node.type, "control_type": node.control_type, **locator_meta},
                        }
                    )
                    current_parent_widget_id = wid

        for c in node.children:
            _visit(c, current_parent_widget_id)

    _visit(collapsed_root, None)
    # 仅做稳定排序；id 已是 locator，不再按序编号
    widget_payloads.sort(key=lambda w: (w["bounds"].y, w["bounds"].x, w["id"]))

    # Build id -> payload map for ancestry derivation
    by_id: dict[str, dict] = {p["id"]: p for p in widget_payloads}

    def _ancestor_roles(widget_id: str, *, limit: int = 6) -> list[str]:
        roles: list[str] = []
        cur_id: str | None = widget_id
        seen: set[str] = set()
        while cur_id and len(roles) < limit:
            if cur_id in seen:
                break
            seen.add(cur_id)
            cur = by_id.get(cur_id)
            if not cur:
                break
            pid = cur.get("parent_id")
            if not pid:
                break
            parent = by_id.get(pid)
            if not parent:
                break
            r = str(parent.get("role") or "").strip()
            if r:
                roles.append(r)
            cur_id = pid
        return roles

    for p in widget_payloads:
        meta = p.get("meta") or {}
        fp = {
            "role": p.get("role"),
            "text": p.get("text_legacy", ""),
            "normalized": p.get("normalized"),
            "automation_id": p.get("automation_id"),
            "ancestor_roles": _ancestor_roles(str(p.get("id") or "")),
        }
        meta["fingerprint"] = fp
        p["meta"] = meta

    for i, payload in enumerate(widget_payloads):
        meta = payload.get("meta") or {}
        # Back-compat debug index (old widgets v1.1 used w_{i})
        meta["legacy_index_id"] = f"w_{i}"
        payload["meta"] = meta
    return [Widget(**payload) for payload in widget_payloads]

