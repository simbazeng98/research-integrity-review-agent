from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
import pytest


def test_batch_intake_cli_ris():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
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
    
    assert result.returncode == 0, result.stderr
    
    csv_table = project_root / "outputs" / "batch_intake" / "batch_intake_table.csv"
    with csv_table.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        
        assert rows[0]["doi"] == "10.0000/toy-retracted"
        assert rows[0]["crossref_update_status"] == "retraction"
        assert rows[0]["title"] == "Room Temperature Superconductivity Myth"
        assert rows[0]["journal"] == "Journal of Anomalous Results"
        assert rows[0]["year"] == "2026"
        
        assert rows[1]["doi"] == "10.0000/toy-eoc"
        assert rows[1]["crossref_update_status"] == "expression_of_concern"
        assert rows[1]["title"] == "A Second Conference Paper"
        assert rows[1]["journal"] == "Proceedings of Superconductivity"
        assert rows[1]["year"] == "2025"
