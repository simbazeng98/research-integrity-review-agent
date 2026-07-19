from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.table_intake import run_table_intake


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
                
    # Five legacy items plus two quantization-grid CSV fixtures.
    assert len(items) == 7
    assert {
        "toy_quantized_timeseries.csv",
        "toy_declared_resolution_timeseries.csv",
    }.issubset({item["source_file"] for item in items})
    
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


def test_table_manifest_csv_neutralizes_formula_strings_but_keeps_numbers(tmp_path):
    input_dir = tmp_path / "tables"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir()
    (input_dir / "=formula.csv").write_text("+COLUMN,normal\nvalue,1\n", encoding="utf-8")

    _, manifest_csv, _, _ = run_table_intake(input_dir, output_dir=output_dir)
    with manifest_csv.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["source_file"] == "'=formula.csv"
    assert row["relative_path"] == "tables/=formula.csv"
    assert row["columns"] == "'+COLUMN, normal"
    assert row["row_count"] == "1"
