from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.report_image_contact_sheet import generate_image_contact_sheet
from integrity_agent.workflows.image_intake import _write_manifest_csv
from integrity_agent.core.images.image_schema import ImageManifestItem


def _write_mock_image_manifest(manifest_jsonl: Path) -> None:
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

    with manifest_jsonl.open("w", encoding="utf-8") as f:
        for item in mock_items:
            f.write(json.dumps(item) + "\n")


def test_generate_image_contact_sheet(tmp_path):
    manifest_jsonl = tmp_path / "image_manifest.jsonl"
    html_file = tmp_path / "contact_sheet.html"

    _write_mock_image_manifest(manifest_jsonl)
            
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

    manifest_jsonl = tmp_path / "image_manifest.jsonl"
    _write_mock_image_manifest(manifest_jsonl)
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


def test_contact_sheet_escapes_text_and_image_attributes(tmp_path):
    manifest_jsonl = tmp_path / "image_manifest.jsonl"
    html_file = tmp_path / "contact_sheet.html"
    attack = 'photo" onerror="alert(1)'
    item = {
        "image_id": "</code><script>alert(1)</script>",
        "file_name": attack,
        "file_ext": "<script>.png",
        "relative_path": r"D:\Private Folder\secret.png",
        "width": 30,
        "height": 30,
        "format": "PNG<script>",
        "sha256": "abc123",
        "warnings": [],
    }
    manifest_jsonl.write_text(json.dumps(item) + "\n", encoding="utf-8")

    out_path = generate_image_contact_sheet(manifest_jsonl, output_path=html_file)
    content = out_path.read_text(encoding="utf-8")

    assert "<script>" not in content
    assert "photo&quot; onerror=&quot;alert(1)" in content
    assert "Failed to render preview" in content
    assert "Private Folder" not in content
    assert "D:%5C" not in content
    assert "D:\\Private" not in content


def test_image_manifest_csv_neutralizes_formula_strings_but_keeps_numbers(tmp_path):
    manifest_csv = tmp_path / "image_manifest.csv"
    item = ImageManifestItem(
        image_id="=IMAGE_ID",
        source_file="+SOURCE",
        relative_path="-RELATIVE",
        file_name="@FILE",
        file_ext=".png",
        file_size_bytes=-12,
        sha256="abc",
        width=30,
        height=40,
        mode="RGB",
        format="PNG",
        warnings=["=WARNING"],
    )

    _write_manifest_csv(manifest_csv, [item])
    with manifest_csv.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["image_id"] == "'=IMAGE_ID"
    assert row["source_file"] == "'+SOURCE"
    assert row["relative_path"] == "'-RELATIVE"
    assert row["file_name"] == "'@FILE"
    assert row["warnings"] == "'=WARNING"
    assert row["file_size_bytes"] == "-12"
