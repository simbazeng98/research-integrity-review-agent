from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
import pytest


def test_image_intake_cli():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "image-intake",
            "examples/toy_image_package/images",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    
    manifest_jsonl = project_root / "outputs" / "image_intake" / "image_manifest.jsonl"
    manifest_csv = project_root / "outputs" / "image_intake" / "image_manifest.csv"
    findings_jsonl = project_root / "outputs" / "image_intake" / "image_findings.jsonl"
    summary_md = project_root / "outputs" / "image_intake" / "image_intake_summary.md"
    
    assert manifest_jsonl.exists()
    assert manifest_csv.exists()
    assert findings_jsonl.exists()
    assert summary_md.exists()
    
    # Verify CSV contents
    with manifest_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 6
        
        img_a = next(r for r in rows if r["file_name"] == "img_a")
        img_copy = next(r for r in rows if r["file_name"] == "img_a_copy")
        assert img_a["sha256"] == img_copy["sha256"]
        assert img_a["width"] == "100"
        
    # Verify findings contain duplicate group
    findings = []
    with findings_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))
                
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "image_exact_duplicate_sha256"
    assert len(findings[0]["evidence_items"]) == 2
