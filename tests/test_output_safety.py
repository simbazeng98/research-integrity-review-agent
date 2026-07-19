from __future__ import annotations

import pytest

from integrity_agent.core.output_safety import resolve_local_asset


@pytest.mark.parametrize(
    "external_path",
    [
        r"D:\Private Folder\secret.png",
        r"D:secret.png",
        r"\\private-server\private-share\secret.png",
        r"\private-root\secret.png",
        "/private-folder/secret.png",
    ],
)
def test_resolve_local_asset_rejects_external_absolute_paths(tmp_path, external_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    assert resolve_local_asset(external_path, project_root=project_root) is None


def test_resolve_local_asset_accepts_project_relative_path(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    resolved = resolve_local_asset("images/example.png", project_root=project_root)

    assert resolved == (project_root / "images" / "example.png").resolve()
