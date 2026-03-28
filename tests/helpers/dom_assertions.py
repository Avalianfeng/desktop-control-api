from __future__ import annotations

from typing import Dict, List, Set


def flatten_elements(root: Dict) -> List[Dict]:
    result: List[Dict] = []
    stack = [root] if root else []
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.get("children", [])))
    return result


def no_cycles_in_tree(root: Dict) -> bool:
    visited: Set[str] = set()
    stack = [root] if root else []
    while stack:
        node = stack.pop()
        node_id = node.get("id", "")
        if node_id in visited:
            return False
        visited.add(node_id)
        stack.extend(node.get("children", []))
    return True


def bounds_are_screen_coordinates(elements: List[Dict]) -> bool:
    for item in elements:
        bounds = item.get("bounds", {})
        required = ("x", "y", "width", "height")
        if not all(k in bounds for k in required):
            return False
        if not all(isinstance(bounds[k], int) for k in required):
            return False
    return True
