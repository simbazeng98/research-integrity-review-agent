from __future__ import annotations

import json
from pathlib import Path
import pytest

from integrity_agent.core.metadata.crossref_client import CrossrefClientError
from integrity_agent.workflows.status_enrich import run_status_enrich
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def test_status_enrich_workflow_offline(tmp_path):
    # 1. Prepare a toy DOI list input file (.txt)
    doi_file = tmp_path / "dois.txt"
    dois = [
        "10.0000/toy-retracted",
        "10.0000/toy-corrected",
        "10.0000/toy-eoc",
        "10.0000/toy-withdrawal",
        "10.0000/toy-update-notice",
        "10.0000/toy-no-update",
        "10.0000/non-existent-doi",  # should be treated as metadata_unavailable
    ]
    doi_file.write_text("\n".join(dois), encoding="utf-8")

    # 2. Run the status enrich workflow
    output_dir = tmp_path / "outputs"
    jsonl_path, summary_path = run_status_enrich(
        input_path=doi_file,
        allow_network=False,
        output_dir=output_dir,
    )

    # 3. Check output paths exist
    assert jsonl_path.exists()
    assert summary_path.exists()

    # 4. Parse the output JSONL and verify EvidenceRecords
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 7

    records = [json.loads(line) for line in lines]

    # Helper to find a record by DOI
    def find_record(doi: str):
        for r in records:
            if r["provenance"]["doi"] == doi:
                return r
        return None

    # Verify retraction
    r_retracted = find_record("10.0000/toy-retracted")
    assert r_retracted is not None
    assert r_retracted["provenance"]["raw_status"] == "retraction"
    assert r_retracted["risk"] == "high"
    assert r_retracted["risk_level"] == "high"
    assert r_retracted["needs_manual_review"] is True
    assert "status context is not proof of misconduct" in r_retracted["summary"]["en"]

    # Verify correction (correction is low risk, not misconduct)
    r_corrected = find_record("10.0000/toy-corrected")
    assert r_corrected is not None
    assert r_corrected["provenance"]["raw_status"] == "correction"
    assert r_corrected["risk"] == "low"
    assert r_corrected["risk_level"] == "low"
    assert r_corrected["needs_manual_review"] is False
    assert "status context is not proof of misconduct" in r_corrected["summary"]["en"]

    # Verify expression of concern
    r_eoc = find_record("10.0000/toy-eoc")
    assert r_eoc is not None
    assert r_eoc["provenance"]["raw_status"] == "expression_of_concern"
    assert r_eoc["risk"] == "medium"
    assert r_eoc["risk_level"] == "medium"
    assert r_eoc["needs_manual_review"] is True

    # Verify withdrawal
    r_withdrawal = find_record("10.0000/toy-withdrawal")
    assert r_withdrawal is not None
    assert r_withdrawal["provenance"]["raw_status"] == "withdrawal"
    assert r_withdrawal["risk"] == "high"
    assert r_withdrawal["risk_level"] == "high"
    assert r_withdrawal["needs_manual_review"] is True

    # Verify update notice
    r_update = find_record("10.0000/toy-update-notice")
    assert r_update is not None
    assert r_update["provenance"]["raw_status"] == "update_notice"
    assert r_update["risk"] == "low"
    assert r_update["risk_level"] == "low"
    assert r_update["needs_manual_review"] is False

    # Verify no known update
    r_no_update = find_record("10.0000/toy-no-update")
    assert r_no_update is not None
    assert r_no_update["provenance"]["raw_status"] == "no_known_update"
    assert r_no_update["risk"] == "low"
    assert r_no_update["risk_level"] == "low"
    assert r_no_update["needs_manual_review"] is False

    # Verify non-existent DOI (offline lookup error)
    r_non_existent = find_record("10.0000/non-existent-doi")
    assert r_non_existent is not None
    assert r_non_existent["provenance"]["raw_status"] == "metadata_unavailable"
    assert r_non_existent["risk"] == "low"
    assert r_non_existent["needs_manual_review"] is False

    # 5. Run validate-ledger CLI function on the output JSONL
    validation_result = validate_ledger_file(jsonl_path)
    assert validation_result.ok is True
    assert validation_result.records == 7


def test_status_enrich_summary_contents(tmp_path):
    # Verify the summary markdown report contains safety notice and details
    doi_file = tmp_path / "dois.txt"
    doi_file.write_text("10.0000/toy-retracted\n10.0000/toy-corrected", encoding="utf-8")

    output_dir = tmp_path / "outputs"
    _, summary_path = run_status_enrich(
        input_path=doi_file,
        allow_network=False,
        output_dir=output_dir,
    )

    summary_content = summary_path.read_text(encoding="utf-8")
    assert "Publication Status Enrichment Summary" in summary_content
    assert "Publication status context is not proof of misconduct." in summary_content
    assert "10.0000/toy-retracted" in summary_content
    assert "retraction" in summary_content
    assert "correction" in summary_content
