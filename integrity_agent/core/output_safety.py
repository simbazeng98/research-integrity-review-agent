from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote


CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_csv_cell(value: Any) -> Any:
    """Neutralize spreadsheet formulas while preserving non-string values."""
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def resolve_local_asset(
    path_value: str | Path,
    *,
    project_root: str | Path,
) -> Path | None:
    """Resolve an asset only when it remains inside the declared project root."""
    root = Path(project_root).resolve()
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def safe_local_asset_url(
    path_value: str | Path,
    *,
    project_root: str | Path,
    output_parent: str | Path,
) -> str | None:
    """Return a quoted relative URL without exposing paths outside the project."""
    root = Path(project_root).resolve()
    output_parent = Path(output_parent).resolve()
    try:
        output_parent.relative_to(root)
    except ValueError:
        return None
    candidate = resolve_local_asset(path_value, project_root=root)
    if candidate is None:
        return None
    try:
        relative = os.path.relpath(candidate, start=output_parent)
    except ValueError:
        return None
    return quote(relative.replace("\\", "/"), safe="/")
