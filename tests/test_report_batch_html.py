from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from integrity_agent.workflows.report_batch_html import generate_batch_html


def test_generate_batch_html(tmp_path):
    jsonl_file = tmp_path / "batch_items.jsonl"
    html_file = tmp_path / "table.html"
    
    mock_items = [
        {
            "item_id": "item-1",
            "title": "A Great Study",
            "doi": "10.0000/toy-retracted",
            "normalized_doi": "10.0000/toy-retracted",
            "year": "2026",
            "journal": "Science",
            "source_format": "ris",
            "crossref_update_status": "retraction",
            "metadata_status": "success",
            "warnings": ["Some warning"]
        },
        {
            "item_id": "item-2",
            "title": "A Stable Study",
            "doi": "10.0000/toy-no-update",
            "normalized_doi": "10.0000/toy-no-update",
            "year": "2025",
            "journal": "Nature",
            "source_format": "ris",
            "crossref_update_status": "no_known_update",
            "metadata_status": "success",
            "warnings": []
        }
    ]
    
    # Write mock batch items
    with jsonl_file.open("w", encoding="utf-8") as f:
        for item in mock_items:
            f.write(json.dumps(item) + "\n")
            
    # Generate HTML
    out_path = generate_batch_html(jsonl_file, output_path=html_file)
    assert out_path.exists()
    
    html_content = out_path.read_text(encoding="utf-8")
    
    # 1. Assert safety disclaimer is in page header
    assert "This table reports metadata review signals only and does not determine research misconduct." in html_content
    
    # 2. Check for styling classes
    assert "<style>" in html_content
    assert ":root {" in html_content
    assert "background-color: var(--bg-color);" in html_content
    
    # 3. Check for parsed elements
    assert "item-1" in html_content
    assert "A Great Study" in html_content
    assert "Science" in html_content
    assert "retraction" in html_content
    assert "Required" in html_content # item-1 is retracted, manual review required
    assert "Some warning" in html_content
    
    assert "item-2" in html_content
    assert "A Stable Study" in html_content
    assert "Nature" in html_content
    assert "no" in html_content.lower()


def test_report_batch_html_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    
    # Generate a batch JSONL first
    result_intake = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "batch-intake",
            "examples/toy_batch_intake/toy_refs.ris",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result_intake.returncode == 0
    
    jsonl_path = project_root / "outputs" / "batch_intake" / "batch_items.jsonl"
    html_path = tmp_path / "review_table_test.html"
    
    # Run HTML generation via CLI
    result_html = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-batch-html",
            str(jsonl_path),
            "-o",
            str(html_path)
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result_html.returncode == 0, result_html.stderr
    assert html_path.exists()
    
    html_content = html_path.read_text(encoding="utf-8")
    assert "This table reports metadata review signals only and does not determine research misconduct." in html_content
