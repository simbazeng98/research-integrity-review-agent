from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

from integrity_agent.workflows.report_image_contact_sheet import generate_image_contact_sheet


def test_generate_image_contact_sheet(tmp_path):
    manifest_jsonl = tmp_path / "image_manifest.jsonl"
    html_file = tmp_path / "contact_sheet.html"
    
    mock_items = [
        {
            "image_id": "img-001",
            "file_name": "img_a",
            "file_ext": ".png",
            "relative_path": "examples/toy_image_package/images/img_a.png",
            "width": 30,
            "height": 30,
            "format": "PNG",
            "sha256": "duplicate-sha256-here",
            "warnings": []
        },
        {
            "image_id": "img-002",
            "file_name": "img_a_copy",
            "file_ext": ".png",
            "relative_path": "examples/toy_image_package/images/img_a_copy.png",
            "width": 30,
            "height": 30,
            "format": "PNG",
            "sha256": "duplicate-sha256-here",
            "warnings": []
        },
        {
            "image_id": "img-003",
            "file_name": "img_corrupt",
            "file_ext": ".png",
            "relative_path": "examples/toy_image_package/images/img_corrupt.png",
            "width": 0,
            "height": 0,
            "format": "unknown",
            "sha256": "error-hash",
            "warnings": ["Failed to read"]
        }
    ]
    
    # Write mock manifest
    with manifest_jsonl.open("w", encoding="utf-8") as f:
        for item in mock_items:
            f.write(json.dumps(item) + "\n")
            
    out_path = generate_image_contact_sheet(manifest_jsonl, output_path=html_file)
    assert out_path.exists()
    
    html_content = out_path.read_text(encoding="utf-8")
    
    # 1. Verify safety disclaimer
    assert "This contact sheet reports image file-level evidence only and does not determine image manipulation or research misconduct." in html_content
    
    # 2. Verify duplicate badges are present
    assert "Exact Duplicate" in html_content
    
    # 3. Verify corrupted/failed badge
    assert "Corrupted / Failed" in html_content
    
    # 4. Verify preview tags and metadata row details
    assert "img_a.png" in html_content
    assert "30 x 30" in html_content
    assert "PNG" in html_content


def test_contact_sheet_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    
    manifest_jsonl = project_root / "outputs" / "image_intake" / "image_manifest.jsonl"
    html_path = tmp_path / "contact_sheet_test.html"
    
    # Run CLI command
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-image-contact-sheet",
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
    assert "This contact sheet reports image file-level evidence only and does not determine image manipulation or research misconduct." in content
