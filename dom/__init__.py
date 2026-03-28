"""Semantic DOM pipeline: filter, normalize, compress."""

from dom.filter import ACTIONABLE_TYPES, is_actionable, is_visible
from dom.normalize import ROLE_MAP, normalize_role
from dom.semantic import build_semantic_dom

__all__ = [
    "ACTIONABLE_TYPES",
    "ROLE_MAP",
    "build_semantic_dom",
    "is_actionable",
    "is_visible",
    "normalize_role",
]
