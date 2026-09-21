"""Helpers for selecting the VACA startup dashboard."""

from collections.abc import Mapping
from typing import Any


def resolve_dashboard_path(
    view_assist_path: str | None, standalone_path: str | None
) -> str:
    """Prefer View Assist, then VACA's standalone dashboard setting."""
    view_assist_path = (view_assist_path or "").strip()
    standalone_path = (standalone_path or "").strip()
    return (view_assist_path or standalone_path).removeprefix("/")


def merge_options(
    existing_options: Mapping[str, Any], submitted_options: Mapping[str, Any]
) -> dict[str, Any]:
    """Preserve omitted options while allowing submitted values to replace them."""
    return {**existing_options, **submitted_options}
