from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

def test_pv_domain_cli_workflow():
    project_root = Path(__file__).resolve().parents[1]
    
    # 1. Run table-intake on examples/toy_pv_package
    result_intake = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "table-intake",
            "examples/toy_pv_package",
            "-o",
            "outputs/table_intake_pv"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result_intake.returncode == 0, result_intake.stderr

    manifest = project_root / "outputs" / "table_intake_pv" / "table_manifest.jsonl"
    profiles = project_root / "outputs" / "table_intake_pv" / "column_profiles.jsonl"
    assert manifest.exists()
    assert profiles.exists()

    # 2. Run pv-domain-review
    result_review = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "pv-domain-review",
            "outputs/table_intake_pv/table_manifest.jsonl",
            "--column-profiles",
            "outputs/table_intake_pv/column_profiles.jsonl",
            "--output-dir",
            "outputs/pv_domain_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result_review.returncode == 0, result_review.stderr

    metric_rows = project_root / "outputs" / "pv_domain_test" / "pv_metric_rows.jsonl"
    field_mapping = project_root / "outputs" / "pv_domain_test" / "pv_field_mapping.jsonl"
    findings = project_root / "outputs" / "pv_domain_test" / "pv_findings.jsonl"
    summary = project_root / "outputs" / "pv_domain_test" / "pv_domain_summary.md"

    assert metric_rows.exists()
    assert field_mapping.exists()
    assert findings.exists()
    assert summary.exists()

    # Check some findings are generated
    findings_list = []
    with findings.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings_list.append(json.loads(line))
    
    assert len(findings_list) > 0
    # verify format
    assert all(f["finding_id"].startswith("PV-FIND-") for f in findings_list)
