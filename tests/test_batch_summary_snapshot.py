from __future__ import annotations

import re
import pytest
from pathlib import Path

from integrity_agent.workflows.batch_intake import run_batch_intake

REQUIRED_SECTIONS = [
    "Batch input source",
    "Number of items parsed",
    "Number of valid DOIs",
    "Number of duplicate DOIs",
    "Metadata lookup mode",
    "Retraction metadata summary",
    "Correction / expression of concern summary",
    "Items requiring manual verification",
    "Limitations",
    "Do-not-overclaim notice"
]

FORBIDDEN_PHRASES = [
    "造假成立",
    "学术不端成立",
    "作者造假",
    "fraud confirmed",
    "misconduct confirmed"
]


def test_batch_summary_snapshot_and_safety_clauses(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    input_path = project_root / "examples" / "toy_batch_intake" / "toy_dois.txt"
    snapshot_path = project_root / "tests" / "snapshots" / "batch_intake_summary_expected.md"
    
    # Run batch intake in temp directory to prevent modifying real outputs
    jsonl, csv, summary_file = run_batch_intake(
        input_path,
        allow_network=False,
        output_dir=tmp_path
    )
    
    report_content = summary_file.read_text(encoding="utf-8")
    expected_content = snapshot_path.read_text(encoding="utf-8")
    
    # 1. Exact match with snapshot (normalize newlines first)
    assert report_content.replace("\r\n", "\n") == expected_content.replace("\r\n", "\n")
    
    # 2. Check for required headers
    for section in REQUIRED_SECTIONS:
        assert f"## {section}" in report_content
        
    # 3. Verify no forbidden overclaiming phrases are present
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in report_content.lower(), f"Report contains forbidden overclaiming language: '{phrase}'"
        
    # 4. Check safety disclosures
    assert "no_known_update` does not prove the paper is reliable" in report_content
    assert "metadata_unavailable` does not imply that the paper is suspicious" in report_content
    assert "correction notice does not imply misconduct" in report_content
