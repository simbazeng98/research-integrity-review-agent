from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from integrity_agent.core.packages.package_schema import ReviewPackageInput
from integrity_agent.workflows.document_claim_intake import (
    DocumentClaimIntakeError,
    run_document_claim_intake,
)


def _claim(claim_id: str, *, human_confirmed: bool = True) -> dict:
    return {
        "claim_id": claim_id,
        "claim_type": "concentration",
        "value": 2,
        "unit": "g/L",
        "device_variant": "control",
        "sample_id": "sample-01",
        "measurement_context": "precursor solution",
        "source_document": "si",
        "source_version": "si-v1",
        "location": "Section S2, sentence 3",
        "source_hash": f"sha256:{claim_id}",
        "human_confirmed": human_confirmed,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_document_claim_intake_writes_normalized_records_and_manifest(tmp_path):
    documents_dir = tmp_path / "review_package" / "documents"
    claims_path = documents_dir / "claims.jsonl"
    _write_jsonl(
        claims_path,
        [
            _claim("confirmed-1"),
            _claim("draft-1", human_confirmed=False),
        ],
    )

    normalized_path, manifest_path = run_document_claim_intake(
        documents_dir,
        output_dir=tmp_path / "outputs",
    )

    records = [
        json.loads(line)
        for line in normalized_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [record["claim_id"] for record in records] == ["confirmed-1", "draft-1"]
    assert records[0]["normalized_value"] == pytest.approx(2.0)
    assert records[0]["normalized_unit"] == "mg/mL"
    assert records[0]["location"] == "Section S2, sentence 3"
    assert records[0]["source_hash"] == "sha256:confirmed-1"
    assert records[1]["record_status"] == "draft_candidate"
    assert records[1]["eligible_for_finding"] is False

    assert manifest["input_record_count"] == 2
    assert manifest["confirmed_claim_count"] == 1
    assert manifest["draft_candidate_count"] == 1
    assert manifest["finding_count"] == 0
    assert manifest["risk_ceiling"] == "medium"
    assert "not a finding" in manifest["safe_report_language"].lower()
    assert manifest["status"] == "warning"
    assert manifest["warnings"]
    assert manifest["automatic_extraction_performed"] is False
    assert str(tmp_path) not in manifest_path.read_text(encoding="utf-8")


def test_document_claim_intake_rejects_invalid_input_without_partial_outputs(tmp_path):
    claims_path = tmp_path / "documents" / "claims.jsonl"
    invalid = _claim("invalid-1")
    del invalid["device_variant"]
    _write_jsonl(claims_path, [invalid])
    output_dir = tmp_path / "outputs"

    with pytest.raises(DocumentClaimIntakeError, match="line 1"):
        run_document_claim_intake(claims_path, output_dir=output_dir)

    assert not (output_dir / "document_claims.jsonl").exists()
    assert not (output_dir / "document_claim_intake_manifest.json").exists()


def test_document_claim_intake_marks_empty_structured_input_as_warning(tmp_path):
    claims_path = tmp_path / "documents" / "claims.jsonl"
    _write_jsonl(claims_path, [])

    _, manifest_path = run_document_claim_intake(claims_path, output_dir=tmp_path / "outputs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "warning"
    assert manifest["input_record_count"] == 0
    assert manifest["warnings"] == ["claims.jsonl contains no claim records"]


def test_document_claim_intake_refuses_unstructured_document_inputs(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-toy")

    with pytest.raises(DocumentClaimIntakeError, match="claims.jsonl"):
        run_document_claim_intake(pdf_path, output_dir=tmp_path / "outputs")


def test_document_claim_intake_cli_is_offline_and_reports_outputs(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    claims_path = tmp_path / "documents" / "claims.jsonl"
    output_dir = tmp_path / "outputs"
    _write_jsonl(claims_path, [_claim("cli-1")])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "document-claim-intake",
            str(claims_path),
            "-o",
            str(output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "document_claims.jsonl").exists()
    assert (output_dir / "document_claim_intake_manifest.json").exists()
    assert "document_claims.jsonl" in result.stdout


def test_review_package_input_has_optional_documents_dir_without_breaking_old_callers():
    package = ReviewPackageInput(package_dir="examples/toy_review_package")

    assert package.documents_dir == "examples/toy_review_package/documents"
    assert package.to_dict()["documents_dir"] == "examples/toy_review_package/documents"
