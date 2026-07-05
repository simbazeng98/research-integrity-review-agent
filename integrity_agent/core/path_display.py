from __future__ import annotations

from pathlib import Path
from typing import Any


def display_path(path: Any, *, root: Path | str | None = None) -> str:
    """Render paths for user-visible CLI/report output.

    Uses repo/current-working-directory-relative POSIX paths when possible and
    avoids leaking local absolute Windows paths in normal CLI messages.
    """
    if path is None:
        return ""
    candidate = Path(path)
    base = Path.cwd() if root is None else Path(root)
    try:
        return candidate.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()
