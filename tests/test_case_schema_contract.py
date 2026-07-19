from __future__ import annotations

import json

import pytest
import yaml

from integrity_agent.core.evidence.schema import Finding
from integrity_agent.workflows.case_distill import (
    CaseValidationError,
    distill_yaml_case,
    validate_case_card,
)
from integrity_agent.workflows.geng_video_distillation import (
    GengVideoSafetyError,
    validate_geng_video_case_card,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def production_card() -> dict:
    return {
        "case_id": "production_case",
        "priority": "P1",
        "source_type": "public_case",
        "source_url": "https://example.test/case",
        "field": "numeric_table_integrity",
        "public_status": "unresolved",
        "evidence_patterns": ["repeated values"],
        "detector_candidates": ["numeric_terminal_digit_anomaly"],
        "manual_verification_needed": ["inspect source data"],
        "false_positive_risks": ["rounding"],
        "safe_report_language": "Candidate risk signal requiring independent verification.",
    }


def geng_card() -> dict:
    return {
        "case_id": "geng_case",
        "source_type": "bilibili_video",
        "source_url": "https://www.bilibili.com/video/BVcase/",
        "bv_id": "BVcase",
        "video_title": "synthetic title",
        "transcript_confidence": "synthetic_fixture",
        "case_kind": "specific_paper_case",
        "field": "numeric_table_integrity",
        "paper_identifiers": [],
        "public_status": "allegation",
        "public_status_basis": "Synthetic test card only.",
        "video_raised_risk_signals": ["candidate numeric anomaly"],
        "evidence_patterns": ["numeric_terminal_digit_cluster"],
        "detector_candidates": ["numeric_terminal_digit_cluster_from_video_cases"],
        "manual_verification_needed": ["original paper and raw data"],
        "false_positive_risks": ["rounding"],
        "safe_report_language": "Candidate risk signal requiring independent verification.",
        "limitations": ["not independently verified"],
        "private_notes_reference": "local_private_note_available_not_public",
    }


def test_production_case_requires_schema_contract_fields():
    incomplete = {
        "case_id": "incomplete_production_case",
        "source_type": "public_case",
        "public_status": "allegation",
    }

    with pytest.raises(CaseValidationError) as exc_info:
        validate_case_card(incomplete)

    message = str(exc_info.value)
    for field in (
        "priority",
        "source_url",
        "evidence_patterns",
        "manual_verification_needed",
        "false_positive_risks",
        "safe_report_language",
    ):
        assert field in message


def test_toy_or_draft_relaxation_requires_explicit_validation_mode():
    toy_card = {
        "case_id": "explicit_toy_case",
        "source_type": "toy_case",
        "public_status": "unresolved",
        "validation_mode": "toy",
    }

    result = validate_case_card(toy_card)

    assert result.card["validation_mode"] == "toy"


def test_safe_report_language_survives_yaml_to_finding_to_ledger(tmp_path):
    card = production_card()
    card["safe_report_language"] = "Unique safe report language must survive this conversion."
    card_path = tmp_path / "production_case.yml"
    card_path.write_text(yaml.safe_dump(card, sort_keys=False), encoding="utf-8")

    finding, warnings = distill_yaml_case(card_path)
    assert not warnings
    assert isinstance(finding, Finding)
    assert finding.safe_report_language == card["safe_report_language"]

    record = finding.to_ledger_record()
    assert record["safe_report_language"] == card["safe_report_language"]
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    assert validate_ledger_file(ledger_path).ok


def test_generic_and_geng_case_paths_share_forbidden_language_and_private_path_guards():
    unsafe_generic = production_card()
    unsafe_generic["safe_report_language"] = "fraud confirmed"  # forbidden phrase fixture
    with pytest.raises(CaseValidationError, match="forbidden phrase"):
        validate_case_card(unsafe_generic)

    unsafe_geng = geng_card()
    unsafe_geng["safe_report_language"] = "fraud confirmed"  # forbidden phrase fixture
    with pytest.raises(GengVideoSafetyError, match="forbidden phrase"):
        validate_geng_video_case_card(unsafe_geng)

    private_generic = production_card()
    private_path = "C:" + "/Users/example/private_transcripts/case.yml"
    private_generic["source_url"] = private_path
    with pytest.raises(CaseValidationError, match="private/local path"):
        validate_case_card(private_generic)

    private_geng = geng_card()
    private_geng["private_notes_reference"] = private_path
    with pytest.raises(GengVideoSafetyError, match="private/local path"):
        validate_geng_video_case_card(private_geng)
