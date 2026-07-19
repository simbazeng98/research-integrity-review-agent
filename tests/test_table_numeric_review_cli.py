from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_table_numeric_review_cli():
    project_root = Path(__file__).resolve().parents[1]
    
    # 1. Run table-intake first to set up files
    subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "table-intake",
            "examples/toy_table_package",
        ],
        cwd=project_root,
        check=True
    )
    
    manifest_jsonl = project_root / "outputs" / "table_intake" / "table_manifest.jsonl"
    
    # 2. Run table-numeric-review
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "table-numeric-review",
            str(manifest_jsonl),
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    findings_jsonl = project_root / "outputs" / "table_intake" / "table_numeric_findings.jsonl"
    summary_md = project_root / "outputs" / "table_intake" / "table_numeric_review_summary.md"
    
    assert findings_jsonl.exists()
    assert summary_md.exists()
    
    # Check findings JSONL
    findings = []
    with findings_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))
                
    assert len(findings) >= 2
    
    rules = [f["rule_id"] for f in findings]
    assert "numeric_fixed_delta_between_columns" in rules
    assert "numeric_terminal_digit_anomaly" in rules
    
    # Verify schema fields are present on each finding
    for f in findings:
        assert "table_id" in f
        assert "source_file" in f
        assert "column_names" in f
        assert "row_range" in f
        assert "risk_level" in f
        assert "safe_report_language" in f
        assert "alternative_explanations" in f
        assert "false_positive_risks" in f
        assert "manual_verification" in f
