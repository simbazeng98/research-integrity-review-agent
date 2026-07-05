from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
import pytest


def test_table_intake_cli():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "table-intake",
            "examples/toy_table_package",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    manifest_jsonl = project_root / "outputs" / "table_intake" / "table_manifest.jsonl"
    manifest_csv = project_root / "outputs" / "table_intake" / "table_manifest.csv"
    profiles_jsonl = project_root / "outputs" / "table_intake" / "column_profiles.jsonl"
    summary_md = project_root / "outputs" / "table_intake" / "table_intake_summary.md"
    
    assert manifest_jsonl.exists()
    assert manifest_csv.exists()
    assert profiles_jsonl.exists()
    assert summary_md.exists()
    
    # Load manifest JSONL
    items = []
    with manifest_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
                
    # We expect 5 items: toy_fixed_delta.csv, toy_terminal_digit.tsv, toy_markdown_table.md,
    # and 2 sheets from toy_multisheet.xlsx (SheetOne, SheetTwo)
    assert len(items) == 5
    
    formats = [item["source_format"] for item in items]
    assert "csv" in formats
    assert "tsv" in formats
    assert "markdown_table" in formats
    assert "xlsx_sheet" in formats
    
    # Load profiles JSONL
    profiles = []
    with profiles_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                profiles.append(json.loads(line))
                
    assert len(profiles) > 0
    assert profiles[0]["table_id"] is not None
    assert profiles[0]["profile"]["column_name"] is not None
