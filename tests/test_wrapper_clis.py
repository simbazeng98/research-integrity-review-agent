from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

def test_init_package_cli(tmp_path):
    pkg_dir = tmp_path / "test_pkg"
    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "init-package", str(pkg_dir)],
        text=True,
        capture_output=True,
        check=True
    )
    assert result.returncode == 0
    assert "Initialized local review package" in result.stdout

    # Assert subdirectories were created
    assert (pkg_dir / "metadata").exists()
    assert (pkg_dir / "images").exists()
    assert (pkg_dir / "tables").exists()
    assert (pkg_dir / "pv").exists()
    assert (pkg_dir / "raw_pv").exists()
    assert (pkg_dir / "references").exists()
    assert (pkg_dir / "metadata" / "doi.txt").exists()


def test_run_audit_cli(tmp_path):
    pkg_dir = tmp_path / "test_pkg"
    # init it
    subprocess.run(
        [sys.executable, "-m", "integrity_agent", "init-package", str(pkg_dir)],
        check=True
    )

    out_dir = tmp_path / "outputs"
    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "run-audit", str(pkg_dir), "-o", str(out_dir)],
        text=True,
        capture_output=True,
        check=True
    )
    assert result.returncode == 0
    assert "Audit run complete" in result.stdout

    # Load unified findings and assert no findings exist
    findings_file = out_dir / "unified_evidence_index.jsonl"
    assert findings_file.exists()
    findings = []
    with open(findings_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))
    assert len(findings) == 0


def test_validate_report_cli(tmp_path):
    findings_file = tmp_path / "findings.jsonl"

    # Write a valid mock finding compliant with ledger schema
    finding = {
        "finding_id": "FIND-001",
        "finding_category": "pv_evidence_completeness",
        "type": "pv_jv_mask_area_completeness",
        "title": "Missing Mask Area",
        "summary": "The table lacks mask area description.",
        "risk": "low",
        "needs_manual_review": True,
        "evidence": [{"source": "toy_pv.csv", "location": "Table 1"}],
        "manual_verification": {"needed": True, "requests": ["Verify the mask."]}
    }
    with findings_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(finding) + "\n")

    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "validate-report", str(findings_file)],
        text=True,
        capture_output=True,
        check=True
    )
    assert result.returncode == 0
    assert "PASSED: Schema validation matches all constraints" in result.stdout
