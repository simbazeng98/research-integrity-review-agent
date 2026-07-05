from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

from integrity_agent.workflows.report_table_review_html import generate_table_review_html


def test_generate_table_review_html(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    manifest_jsonl = project_root / "outputs" / "table_intake" / "table_manifest.jsonl"
    html_file = tmp_path / "table_review_dashboard.html"
    
    out_path = generate_table_review_html(manifest_jsonl, output_path=html_file)
    assert out_path.exists()
    
    content = out_path.read_text(encoding="utf-8")
    
    # 1. Verify safety notice
    assert "This dashboard reports source-data table signals only and does not determine data fabrication or research misconduct." in content
    
    # 2. Verify table content and badges are listed
    assert "tbl-001" in content
    assert "toy_fixed_delta.csv" in content
    assert "No Findings" in content or "fixed delta" in content


def test_table_review_html_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    manifest_jsonl = project_root / "outputs" / "table_intake" / "table_manifest.jsonl"
    html_path = tmp_path / "dashboard_cli.html"
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-table-review-html",
            str(manifest_jsonl),
            "-o",
            str(html_path)
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    assert html_path.exists()
    
    content = html_path.read_text(encoding="utf-8")
    assert "This dashboard reports source-data table signals only and does not determine data fabrication or research misconduct." in content
