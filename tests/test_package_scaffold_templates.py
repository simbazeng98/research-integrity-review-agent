from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from integrity_agent.core.safety import find_runtime_safety_issues


EXPECTED_TEMPLATES = (
    "PACKAGE_GUIDE.md",
    "documents/claims.example.jsonl",
    "documents/version_manifest.example.yml",
    "documents/decay_fit_records.example.jsonl",
    "documents/curve_reconciliations.example.yml",
    "documents/materials_process_lineage.example.yml",
)


def _run_init(package_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "integrity_agent", "init-package", str(package_dir)],
        text=True,
        capture_output=True,
        check=True,
    )


def test_init_package_creates_safe_human_confirmation_templates(tmp_path: Path) -> None:
    package_dir = tmp_path / "review-package"

    result = _run_init(package_dir)

    assert "Start with PACKAGE_GUIDE.md" in result.stdout
    for relative_path in EXPECTED_TEMPLATES:
        assert (package_dir / relative_path).is_file()

    claim = json.loads(
        (package_dir / "documents/claims.example.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    decay = json.loads(
        (package_dir / "documents/decay_fit_records.example.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    version = yaml.safe_load(
        (package_dir / "documents/version_manifest.example.yml").read_text(
            encoding="utf-8"
        )
    )
    curves = yaml.safe_load(
        (package_dir / "documents/curve_reconciliations.example.yml").read_text(
            encoding="utf-8"
        )
    )
    lineage = yaml.safe_load(
        (package_dir / "documents/materials_process_lineage.example.yml").read_text(
            encoding="utf-8"
        )
    )

    assert claim["human_confirmed"] is False
    assert decay["human_confirmed"] is False
    assert version["events"] == []
    assert curves["reconciliations"][0]["segment_similarity"][
        "human_confirmed_independent_curves"
    ] is False
    assert lineage["records"][0]["human_confirmed"] is False
    assert find_runtime_safety_issues([claim, decay, version, curves, lineage]) == []

    # Example names are intentionally inert until a reviewer copies and confirms them.
    assert not (package_dir / "documents/claims.jsonl").exists()
    assert not (package_dir / "documents/version_manifest.yml").exists()


def test_init_package_does_not_overwrite_existing_starter_files(tmp_path: Path) -> None:
    package_dir = tmp_path / "review-package"
    package_dir.mkdir()
    guide = package_dir / "PACKAGE_GUIDE.md"
    guide.write_text("my notes\n", encoding="utf-8")

    _run_init(package_dir)

    assert guide.read_text(encoding="utf-8") == "my notes\n"
