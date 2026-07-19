from __future__ import annotations

import json

import pytest
import yaml

from integrity_agent.workflows.case_distill import (
    CaseValidationError,
    distill_yaml_case,
    validate_case_card,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _production_card() -> dict:
    return {
        "case_id": "public_method_case",
        "priority": "P1",
        "source_type": "public_method",
        "source_url": "https://www.xiaohongshu.com/explore/toy-feed-id",
        "field": "numeric_table_integrity",
        "scope": "research_integrity",
        "public_status": "public_method_example",
        "target_doi": "10.1000/toy-doi",
        "source_accessed_at": "2026-07-11",
        "evidence_tier": "E1",
        "resolution_status": "unresolved",
        "counter_sources": [],
        "evidence_patterns": ["candidate repeated-value grid"],
        "detector_candidates": ["measurement_precision_anomaly"],
        "manual_verification_needed": ["inspect source data"],
        "false_positive_risks": ["instrument resolution"],
        "safe_report_language": "Candidate risk signal requiring independent verification.",
        "limitations": [
            "Social claims and commenter identities are not independently verified."
        ],
    }


@pytest.mark.parametrize("tier", ["E-1", "E5", "publisher", 2])
def test_public_method_card_rejects_invalid_evidence_tier(tier):
    card = _production_card()
    card["evidence_tier"] = tier

    with pytest.raises(CaseValidationError, match="evidence_tier"):
        validate_case_card(card)


@pytest.mark.parametrize(
    "field",
    ["target_doi", "source_accessed_at", "evidence_tier", "resolution_status", "scope"],
)
def test_public_method_card_requires_paper_provenance(field):
    card = _production_card()
    card.pop(field)

    with pytest.raises(CaseValidationError, match=field):
        validate_case_card(card)


def test_public_method_card_rejects_invalid_doi_and_access_timestamp():
    card = _production_card()
    card["target_doi"] = "not-a-doi"
    card["source_accessed_at"] = "11/07/2026"

    with pytest.raises(CaseValidationError) as exc_info:
        validate_case_card(card)

    assert "target_doi" in str(exc_info.value)
    assert "source_accessed_at" in str(exc_info.value)


@pytest.mark.parametrize(
    "counter_sources, expected_error",
    [
        ("https://example.test/response", "counter_sources"),
        ([{"source_type": "author_response", "observed_at": "2026-07-11"}], "url"),
        ([{"url": "https://example.test", "observed_at": "2026-07-11"}], "source_type"),
        (
            [
                {
                    "url": "https://example.test",
                    "source_type": "social_reply",
                    "observed_at": "2026-07-11",
                }
            ],
            "source_type",
        ),
        (
            [
                {
                    "url": "https://example.test",
                    "source_type": "author_response",
                    "observed_at": "yesterday",
                }
            ],
            "observed_at",
        ),
    ],
)
def test_counter_sources_have_structured_provenance(counter_sources, expected_error):
    card = _production_card()
    card["counter_sources"] = counter_sources

    with pytest.raises(CaseValidationError, match=expected_error):
        validate_case_card(card)


@pytest.mark.parametrize("status", ["resolved_by_version", "formally_corrected"])
def test_resolved_status_requires_counter_source(status):
    card = _production_card()
    card["resolution_status"] = status

    with pytest.raises(CaseValidationError, match="counter source"):
        validate_case_card(card)


@pytest.mark.parametrize("status", ["resolved_by_version", "formally_corrected"])
def test_author_response_alone_cannot_establish_publisher_resolution(status):
    card = _production_card()
    card["resolution_status"] = status
    card["counter_sources"] = [
        {
            "url": "https://example.test/author-response",
            "source_type": "author_response",
            "observed_at": "2026-07-11",
        }
    ]

    with pytest.raises(CaseValidationError, match="publisher"):
        validate_case_card(card)


def test_author_response_can_mark_case_partially_explained():
    card = _production_card()
    card["resolution_status"] = "partially_explained"
    card["counter_sources"] = [
        {
            "url": "https://example.test/author-response",
            "source_type": "author_response",
            "observed_at": "2026-07-11",
        }
    ]

    assert validate_case_card(card).card["resolution_status"] == "partially_explained"


@pytest.mark.parametrize(
    "timeline",
    [
        "2026-07-11: response",
        [{"source_type": "author_response", "observed_at": "not-a-date"}],
        ["response"],
    ],
)
def test_version_timeline_requires_compatible_structured_entries(timeline):
    card = _production_card()
    card["version_timeline"] = timeline

    with pytest.raises(CaseValidationError, match="version_timeline"):
        validate_case_card(card)


def test_public_method_status_cannot_be_promoted_to_formal_misconduct_status():
    card = _production_card()
    card["public_status"] = "confirmed_misconduct"
    card["official_or_institutional_source"] = "https://example.test/official"

    with pytest.raises(CaseValidationError, match="public_method"):
        validate_case_card(card)


def test_existing_non_social_case_cards_remain_backward_compatible():
    card = _production_card()
    card["source_type"] = "public_case"
    for field in (
        "target_doi",
        "source_accessed_at",
        "evidence_tier",
        "resolution_status",
        "counter_sources",
    ):
        card.pop(field)

    assert validate_case_card(card).card == card


def test_counter_evidence_state_survives_yaml_to_ledger_provenance(tmp_path):
    card = _production_card()
    card.update(
        {
            "source_snapshot_hash": "sha256:0123456789abcdef",
            "resolution_status": "partially_explained",
            "counter_sources": [
                {
                    "url": "https://example.test/author-response",
                    "source_type": "author_response",
                    "observed_at": "2026-07-11",
                }
            ],
            "version_timeline": [
                {
                    "source_url": "https://example.test/author-response",
                    "source_type": "author_response",
                    "observed_at": "2026-07-11",
                    "status": "response_observed",
                }
            ],
        }
    )
    path = tmp_path / "public_method.yml"
    path.write_text(yaml.safe_dump(card, sort_keys=False), encoding="utf-8")

    finding, warnings = distill_yaml_case(path)
    record = finding.to_ledger_record()

    assert not warnings
    for field in (
        "target_doi",
        "source_accessed_at",
        "source_snapshot_hash",
        "evidence_tier",
        "counter_sources",
        "resolution_status",
        "version_timeline",
    ):
        assert record["provenance"][field] == card[field]

    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    assert validate_ledger_file(ledger_path).ok
