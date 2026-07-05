from __future__ import annotations

import json
import csv
import subprocess
import sys
from pathlib import Path
import pytest


def test_batch_intake_cli_txt():
    project_root = Path(__file__).resolve().parents[1]
    
    # Run batch-intake on toy_dois.txt
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "batch-intake",
            "examples/toy_batch_intake/toy_dois.txt",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    
    jsonl = project_root / "outputs" / "batch_intake" / "batch_items.jsonl"
    csv_table = project_root / "outputs" / "batch_intake" / "batch_intake_table.csv"
    summary_md = project_root / "outputs" / "batch_intake" / "batch_intake_summary.md"
    
    assert jsonl.exists()
    assert csv_table.exists()
    assert summary_md.exists()
    
    # Verify CSV headers and some contents
    with csv_table.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 4
        assert rows[0]["doi"] == "10.0000/toy-retracted"
        assert rows[0]["crossref_update_status"] == "retraction"
        assert rows[1]["doi"] == "10.0000/toy-no-update"
        assert rows[1]["crossref_update_status"] == "no_known_update"
        assert rows[2]["doi"] == "10.0000/toy-corrected"
        assert rows[2]["crossref_update_status"] == "correction"
        assert rows[3]["doi"] == "invalid-doi-here"
        assert rows[3]["crossref_update_status"] == "metadata_unavailable"
        assert "Invalid DOI" in rows[3]["warnings"]


def test_batch_intake_cli_json():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "batch-intake",
            "examples/toy_batch_intake/toy_zotero_csl.json",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    
    csv_table = project_root / "outputs" / "batch_intake" / "batch_intake_table.csv"
    with csv_table.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["doi"] == "10.0000/toy-eoc"
        assert rows[0]["crossref_update_status"] == "expression_of_concern"
        assert rows[0]["title"] == "Room Temp Superconductivity"
        assert rows[1]["doi"] == "10.0000/toy-no-update"
        assert rows[1]["crossref_update_status"] == "no_known_update"
        assert rows[1]["title"] == "A Stable Synthesis"


def test_batch_intake_cli_bib():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "batch-intake",
            "examples/toy_batch_intake/toy_refs.bib",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    
    csv_table = project_root / "outputs" / "batch_intake" / "batch_intake_table.csv"
    with csv_table.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["doi"] == "10.0000/toy-corrected"
        assert rows[0]["crossref_update_status"] == "correction"
        assert rows[0]["journal"] == "Journal of Applied Physics"
        assert rows[1]["doi"] == "10.0000/toy-retracted"
        assert rows[1]["crossref_update_status"] == "retraction"
        assert rows[1]["journal"] == "Nature Materials"
