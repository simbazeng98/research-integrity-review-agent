from __future__ import annotations

import json
from pathlib import Path
from integrity_agent.workflows.report_reader_review import write_reader_review_report


def test_reader_report_table_integration(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    
    findings_jsonl = tmp_path / "rule_findings.jsonl"
    report_file = tmp_path / "reader_review_report.md"
    
    # Write empty rule findings
    findings_jsonl.write_text("", encoding="utf-8")
    
    # In the workspace, outputs/table_intake/table_numeric_findings.jsonl has been generated
    # from our prior test steps, so it will be loaded.
    out_report = write_reader_review_report(findings_jsonl, output_path=report_file)
    assert out_report.exists()
    
    content = out_report.read_text(encoding="utf-8")
    
    # 1. Verify table numeric findings are present
    assert "numeric_fixed_delta_between_columns" in content
    assert "numeric_terminal_digit_anomaly" in content
    assert "toy_fixed_delta.csv" in content
    assert "toy_terminal_digit.tsv" in content
    
    # 2. Verify questions and explanations
    assert "Please clarify whether tabular columns represent independent measurements" in content
    assert "Please provide the raw spreadsheets and formula scripts" in content
    assert "table numeric checks are limited to" in content
