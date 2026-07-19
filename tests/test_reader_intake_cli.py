from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.reader_intake import run_reader_intake


def test_run_reader_intake_workflow(tmp_path):
    meta_path, summary_path = run_reader_intake(
        doi_input="10.0000/toy-retracted",
        allow_network=False,
        output_dir=tmp_path
    )
    
    assert meta_path.exists()
    assert summary_path.exists()
    
    # Check metadata contents
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["normalized_doi"] == "10.0000/toy-retracted"
    assert meta["status"] == "retraction"
    assert meta["source_strength"] == "toy_or_synthetic"
    assert meta["title"] == "Mock Retracted Article"
    assert len(meta["updates"]) == 1
    
    # Check summary contents
    summary = summary_path.read_text(encoding="utf-8")
    assert "# Paper Case Intake Summary" in summary
    assert "Target DOI: `10.0000/toy-retracted`" in summary
    assert "Status: `retraction`" in summary
    assert "**RETRACTION** notice" in summary
    assert "does not determine misconduct" in summary


def test_reader_intake_cli_subprocess(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    
    # Test CLI call via subprocess
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "reader-intake",
            "--doi",
            "10.0000/toy-corrected",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    
    meta_path = project_root / "outputs" / "paper_case" / "metadata.json"
    summary_path = project_root / "outputs" / "paper_case" / "intake_summary.md"
    
    assert meta_path.exists()
    assert summary_path.exists()
    
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "correction"
    
    summary = summary_path.read_text(encoding="utf-8")
    assert "Status: `correction`" in summary
    assert "does not determine misconduct" in summary
