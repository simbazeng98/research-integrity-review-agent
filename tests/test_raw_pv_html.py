from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_raw_pv_html_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-raw-pv-html",
            "outputs/raw_pv_test/raw_pv_findings.jsonl",
            "-o",
            "outputs/raw_pv_test/raw_pv_dashboard.html"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    html_file = project_root / "outputs" / "raw_pv_test" / "raw_pv_dashboard.html"
    assert html_file.exists()
    
    html_content = html_file.read_text(encoding="utf-8")
    assert "Raw PV &amp; Materials Recalculation Dashboard" in html_content or "Raw PV & Materials Recalculation Dashboard" in html_content
    assert "Safety Notice" in html_content
