from __future__ import annotations

import json
import shutil
from pathlib import Path

from integrity_agent.workflows.review_package import run_review_package
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _status(summary, module_name: str) -> dict:
    return next(
        item.to_dict()
        for item in summary.module_statuses
        if item.module_name == module_name
    )


def test_review_package_runs_claim_comparison_and_version_reconciliation(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    package_dir = tmp_path / "package"
    shutil.copytree(
        project_root / "examples" / "toy_review_package" / "documents",
        package_dir / "documents",
    )
    output_dir = tmp_path / "output"

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    intake_path = output_dir / "document_claim_intake" / "document_claims.jsonl"
    crossdoc_path = output_dir / "cross_document_review" / "cross_document_findings.jsonl"
    version_path = output_dir / "version_reconciliation" / "reconciled_findings.jsonl"
    unified_path = output_dir / "unified_evidence_index.jsonl"
    assert intake_path.exists()
    assert crossdoc_path.exists()
    assert version_path.exists()
    assert validate_ledger_file(unified_path).ok

    crossdoc = _records(crossdoc_path)
    assert len(crossdoc) == 1
    assert crossdoc[0]["rule_id"] == "cross_document_claim_consistency"
    assert set(crossdoc[0]["provenance"]["related_claim_ids"]) == {
        "toy-concentration-main",
        "toy-concentration-si",
    }

    reconciled = _records(version_path)
    assert len(reconciled) == 1
    assert reconciled[0]["resolution_status"] == "resolved_by_version"
    assert reconciled[0]["historical"] is True
    assert reconciled[0]["open_for_scoring"] is False
    assert reconciled[0]["mrpi_eligible"] is False

    unified = _records(unified_path)
    crossdoc_unified = [
        item
        for item in unified
        if item.get("rule_id") == "cross_document_claim_consistency"
    ]
    assert len(crossdoc_unified) == 1
    assert crossdoc_unified[0]["resolution_status"] == "resolved_by_version"
    assert not any(
        item.get("risk_level") == "medium" and item.get("open_for_scoring", True)
        for item in crossdoc_unified
    )
    assert summary.mrpi == 0.0

    intake_status = _status(summary, "document-claim-intake")
    assert intake_status["input_artifact_count"] == 1
    assert intake_status["parsed_row_count"] == 5
    assert intake_status["finding_count"] == 0
    crossdoc_status = _status(summary, "cross-document-review")
    assert crossdoc_status["parsed_row_count"] == 5
    assert crossdoc_status["finding_count"] == 1
    version_status = _status(summary, "version-reconciliation")
    assert version_status["finding_count"] == 1


def test_review_package_without_documents_remains_a_clean_skip(tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(tmp_path / "output"),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    for module_name in (
        "document-claim-intake",
        "cross-document-review",
        "version-reconciliation",
    ):
        status = _status(summary, module_name)
        assert status["status"] == "skipped"
        assert status["input_artifact_count"] == 0
        assert status["parsed_row_count"] == 0
        assert status["finding_count"] == 0
        assert status["skip_reason"] == "no_input_artifacts"
