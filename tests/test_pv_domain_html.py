from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.report_pv_domain_html import generate_pv_domain_html

def test_pv_domain_html_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    findings = tmp_path / "pv_findings.jsonl"
    dashboard = tmp_path / "pv_domain_dashboard.html"
    findings.write_text("", encoding="utf-8")
    
    # Run report-pv-domain-html
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-pv-domain-html",
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

    content = dashboard.read_text(encoding="utf-8")
    assert "Photovoltaics &amp; Materials Domain Review" in content or "Photovoltaics & Materials Domain Review" in content
    assert "Safety Notice" in content


def test_pv_domain_html_escapes_untrusted_fields_and_stays_offline(tmp_path):
    findings = tmp_path / "pv_findings.jsonl"
    dashboard = tmp_path / "pv_domain_dashboard.html"
    attack = '</strong><script>alert("xss")</script>'
    finding = {
        "finding_id": f"PV-001{attack}",
        "rule_id": f"pv_pce_consistency{attack}",
        "risk_level": 'high" onmouseover="alert(1)',
        "source_file": f"devices{attack}.csv",
        "table_id": f"table{attack}",
        "row_index": attack,
        "device_id": f"device{attack}",
        "observed_values": {attack: attack},
        "recomputed_values": {"value": attack},
        "safe_report_language": attack,
        "manual_verification": [attack],
    }
    findings.write_text(json.dumps(finding) + "\n", encoding="utf-8")

    generate_pv_domain_html(findings, dashboard)
    content = dashboard.read_text(encoding="utf-8")

    assert "<script>" not in content
    assert 'onmouseover="alert(1)' not in content
    assert "&lt;script&gt;alert" in content
    assert 'class="finding-row risk-low"' in content
    assert 'class="risk-badge badge-low"' in content
    assert "fonts.googleapis.com" not in content
    assert "fonts.gstatic.com" not in content
