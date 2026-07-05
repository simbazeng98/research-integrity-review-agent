from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_pv_domain_html_cli():
    project_root = Path(__file__).resolve().parents[1]
    
    # Run report-pv-domain-html
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-pv-domain-html",
            "outputs/pv_domain_test/pv_findings.jsonl",
            "-o",
            "outputs/pv_domain_test/pv_domain_dashboard.html"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr

    dashboard = project_root / "outputs" / "pv_domain_test" / "pv_domain_dashboard.html"
    assert dashboard.exists()

    content = dashboard.read_text(encoding="utf-8")
    assert "Photovoltaics &amp; Materials Domain Review" in content or "Photovoltaics & Materials Domain Review" in content
    assert "Safety Notice" in content
