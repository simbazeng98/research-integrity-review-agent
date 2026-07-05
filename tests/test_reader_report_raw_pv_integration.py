from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

def test_reader_report_raw_pv_integration():
    project_root = Path(__file__).resolve().parents[1]
    
    # 1. Ensure findings from the CLI runs exist
    src_findings = project_root / "outputs" / "raw_pv_test" / "raw_pv_findings.jsonl"
    dest_findings = project_root / "outputs" / "raw_pv" / "raw_pv_findings.jsonl"
    dest_findings.parent.mkdir(parents=True, exist_ok=True)
    if src_findings.exists():
        shutil.copy(src_findings, dest_findings)
        
    src_summary = project_root / "outputs" / "raw_pv_test" / "raw_pv_reconciliation_summary.md"
    dest_summary = project_root / "outputs" / "raw_pv" / "raw_pv_reconciliation_summary.md"
    if src_summary.exists():
        shutil.copy(src_summary, dest_summary)

    # 2. Run report-reader-review
    findings_path = project_root / "outputs" / "raw_pv_test" / "raw_pv_findings.jsonl"
    output_path = project_root / "outputs" / "reader_review_report_raw_pv.md"
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-reader-review",
            str(findings_path),
            "--output",
            str(output_path)
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    assert output_path.exists()

    report_content = output_path.read_text(encoding="utf-8")
    
    # 3. Check for raw PV section headers
    assert "## Raw photovoltaic measurement recalculation signals" in report_content
    assert "### J–V metric recalculation signals" in report_content
    assert "### J–V hysteresis candidate signals" in report_content
    assert "### EQE spectrum integration signals" in report_content
    assert "### Raw/reported metric reconciliation signals" in report_content
    assert "### Spreadsheet formula audit signals" in report_content
    assert "### Raw PV verification questions" in report_content

    # 4. Confirm NO forbidden overclaiming phrases are present
    for phrase in ["造假成立", "学术不端成立", "作者造假", "fraud confirmed", "misconduct confirmed"]:
        assert phrase not in report_content, f"Forbidden phrase found: '{phrase}'"
