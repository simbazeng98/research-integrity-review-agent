from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.report_raw_pv_html import run_report_raw_pv_html

def test_raw_pv_html_cli_run(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    findings = tmp_path / "raw_pv_findings.jsonl"
    dashboard = tmp_path / "raw_pv_dashboard.html"
    findings.write_text("", encoding="utf-8")
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-raw-pv-html",
            str(findings),
            "-o",
            str(dashboard),
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    assert dashboard.exists()
    
    html_content = dashboard.read_text(encoding="utf-8")
    assert "Raw PV &amp; Materials Recalculation Dashboard" in html_content or "Raw PV & Materials Recalculation Dashboard" in html_content
    assert "Safety Notice" in html_content


def test_raw_pv_html_escapes_untrusted_fields_and_stays_offline(tmp_path):
    findings = tmp_path / "raw_pv_findings.jsonl"
    dashboard = tmp_path / "raw_pv_dashboard.html"
    attack = '</code><script>alert("xss")</script>'
    finding = {
        "finding_id": f"RAW-001{attack}",
        "rule_id": f"pv_source_reconciliation{attack}",
        "detector_id": f"detector{attack}",
        "risk_level": 'medium" onmouseover="alert(1)',
        "device_id": f"device{attack}",
        "source_file": f"measurement{attack}.csv",
        "observed_values": {"label": attack},
        "recomputed_values": {},
        "safe_report_language": attack,
        "alternative_explanations": [attack],
        "false_positive_risks": [attack],
        "manual_verification": [attack],
        "limitations": [attack],
    }
    findings.write_text(json.dumps(finding) + "\n", encoding="utf-8")

    run_report_raw_pv_html(str(findings), str(dashboard))
    content = dashboard.read_text(encoding="utf-8")

    assert "<script>" not in content
    assert 'onmouseover="alert(1)' not in content
    assert "&lt;script&gt;alert" in content
    assert 'class="badge badge-low"' in content
    assert "fonts.googleapis.com" not in content
    assert "fonts.gstatic.com" not in content
