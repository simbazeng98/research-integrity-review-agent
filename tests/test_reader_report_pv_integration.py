from __future__ import annotations

import json
from pathlib import Path
import shutil
from integrity_agent.workflows.report_reader_review import write_reader_review_report

def test_reader_report_pv_integration(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    
    findings_jsonl = tmp_path / "rule_findings.jsonl"
    report_file = tmp_path / "reader_review_report.md"
    
    # Write empty rule findings
    findings_jsonl.write_text("", encoding="utf-8")
    
    # Copy pv_findings.jsonl to outputs/pv_domain/pv_findings.jsonl in workspace if not already done
    pv_src = project_root / "outputs" / "pv_domain_test" / "pv_findings.jsonl"
    pv_dest = project_root / "outputs" / "pv_domain" / "pv_findings.jsonl"
    
    if pv_src.exists():
        pv_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(pv_src, pv_dest)
        
    out_report = write_reader_review_report(findings_jsonl, output_path=report_file)
    assert out_report.exists()
    
    content = out_report.read_text(encoding="utf-8")
    
    # 1. Verify PV section headers
    assert "## Photovoltaics / materials domain evidence signals" in content
    assert "### PV metric consistency signals" in content
    assert "### EQE/J–V current-density signals" in content
    assert "### Voc-loss / bandgap signals" in content
    assert "### Solar-cell reporting completeness gaps" in content
    assert "### Stability reporting gaps" in content
    assert "### Tandem PV consistency signals" in content
    assert "### Materials characterization metadata gaps" in content
    assert "### PV/materials verification questions" in content

    # 2. Verify forbidden phrases are NOT present
    for phrase in ["造假成立", "学术不端成立", "作者造假", "fraud confirmed", "misconduct confirmed"]:
        assert phrase not in content, f"Forbidden phrase found: '{phrase}'"
