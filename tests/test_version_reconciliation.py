from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from integrity_agent.core.claims.version_schema import (
    ResolutionStatus,
    VersionManifest,
    VersionSourceType,
    load_version_manifest,
    source_precedence,
)
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.registry import run_detector
from integrity_agent.workflows.validate_ledger import validate_ledger_file
from integrity_agent.workflows.version_reconciliation import reconcile_version_manifest
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi


def _finding(*, finding_id: str = "crossdoc-1", source_version: str = "si-v1") -> dict:
    return {
        "finding_id": finding_id,
        "type": "visible_consistency_issue",
        "finding_category": "cross_document_claim_consistency",
        "title": "Human-confirmed cross-document value mismatch",
        "summary": "Two human-confirmed source locations show different values.",
        "safe_report_language": (
            "A visible consistency issue requires source-version and context review."
        ),
        "risk": "medium",
        "risk_level": "medium",
        "needs_manual_review": True,
        "manual_verification": {
            "needed": True,
            "requests": ["Compare the identified source versions and publisher record."],
        },
        "evidence": [
            {
                "source": "documents/claims.jsonl",
                "location": "claim-main-1 vs claim-si-1",
            }
        ],
        "false_positive_risks": ["The supplementary file may be stale."],
        "alternative_explanations": ["A later publisher version may align the values."],
        "limitations": ["Only the listed human-confirmed claims were compared."],
        "source_version": source_version,
        "provenance": {
            "rule_id": "cross_document_claim_consistency",
            "source_version": source_version,
            "version_event_id": "observed-v1",
            "related_claim_ids": ["claim-main-1", "claim-si-1"],
        },
    }


def _manifest(events: list[dict]) -> VersionManifest:
    return VersionManifest.model_validate(
        {
            "manifest_version": "1",
            "target_doi": "10.1000/toy-version",
            "events": events,
        }
    )


def _observed_event() -> dict:
    return {
        "event_id": "observed-v1",
        "source_version": "si-v1",
        "source_type": "original_public_version",
        "source_url": "https://publisher.example/article/si-v1",
        "observed_at": "2026-01-10",
        "status": "mismatch_observed",
        "related_finding_ids": ["crossdoc-1"],
        "related_claim_ids": ["claim-main-1", "claim-si-1"],
    }


def test_source_precedence_is_status_authority_not_truth_judgment():
    ordered = sorted(
        list(VersionSourceType),
        key=source_precedence,
    )

    assert ordered.index(VersionSourceType.PUBLISHER_CORRECTION) < ordered.index(
        VersionSourceType.CURRENT_PUBLISHER_ARTICLE
    )
    assert ordered.index(VersionSourceType.CURRENT_PUBLISHER_SI) < ordered.index(
        VersionSourceType.ORIGINAL_PUBLIC_VERSION
    )
    assert ordered.index(VersionSourceType.ORIGINAL_PUBLIC_VERSION) < ordered.index(
        VersionSourceType.AUTHOR_RESPONSE
    )
    assert ordered.index(VersionSourceType.AUTHOR_RESPONSE) < ordered.index(
        VersionSourceType.THIRD_PARTY_SOCIAL
    )


def test_author_response_cannot_claim_publisher_resolution_in_manifest():
    response = {
        "event_id": "response-1",
        "source_version": "author-response-v1",
        "source_type": "author_response",
        "source_url": "https://author.example/response",
        "observed_at": "2026-02-01",
        "status": "response_received",
        "resolution_status": "formally_corrected",
        "resolves_event_ids": ["observed-v1"],
    }

    with pytest.raises(ValidationError, match="author response"):
        _manifest([_observed_event(), response])


def test_author_response_partially_explains_but_does_not_erase_open_issue():
    response = {
        "event_id": "response-1",
        "source_version": "author-response-v1",
        "source_type": "author_response",
        "source_url": "https://author.example/response",
        "observed_at": "2026-02-01",
        "status": "response_received",
        "resolves_event_ids": ["observed-v1"],
    }
    result = reconcile_version_manifest(
        _manifest([_observed_event(), response]),
        findings=[_finding()],
    )

    assert result.resolution_status is ResolutionStatus.PARTIALLY_EXPLAINED
    assert result.publisher_confirmation is False
    assert result.open_medium_finding_count == 1
    assert len(result.timeline) == 2
    reconciled = result.reconciled_findings[0]
    assert reconciled["resolution_status"] == "partially_explained"
    assert reconciled["open_for_scoring"] is True
    assert reconciled["mrpi_eligible"] is True
    assert reconciled["historical"] is False
    assert reconciled["counter_evidence"][0]["source_type"] == "author_response"


def test_verified_publisher_correction_preserves_history_without_open_duplicate(
    tmp_path: Path,
):
    response = {
        "event_id": "response-1",
        "source_version": "author-response-v1",
        "source_type": "author_response",
        "source_url": "https://author.example/response",
        "observed_at": "2026-02-01",
        "status": "response_received",
        "resolves_event_ids": ["observed-v1"],
    }
    correction = {
        "event_id": "publisher-correction-1",
        "source_version": "publisher-correction-v1",
        "source_type": "publisher_correction",
        "source_url": "https://publisher.example/article/correction",
        "observed_at": "2026-03-15",
        "status": "correction_published",
        "resolution_status": "formally_corrected",
        "resolves_event_ids": ["observed-v1"],
    }
    result = reconcile_version_manifest(
        _manifest([correction, _observed_event(), response]),
        findings=[_finding()],
    )

    assert [item["event_id"] for item in result.timeline] == [
        "observed-v1",
        "response-1",
        "publisher-correction-1",
    ]
    assert result.resolution_status is ResolutionStatus.FORMALLY_CORRECTED
    assert result.publisher_confirmation is True
    assert result.open_medium_finding_count == 0
    assert result.historical_finding_count == 1
    reconciled = result.reconciled_findings[0]
    assert reconciled["risk_level"] == "medium"  # historical severity is preserved
    assert reconciled["resolution_status"] == "formally_corrected"
    assert reconciled["historical"] is True
    assert reconciled["open_for_scoring"] is False
    assert reconciled["mrpi_eligible"] is False
    assert calculate_mrpi(result.reconciled_findings) == 0.0

    ledger_path = tmp_path / "reconciled.jsonl"
    ledger_path.write_text(json.dumps(reconciled) + "\n", encoding="utf-8")
    assert validate_ledger_file(ledger_path).ok


def test_linked_publisher_correction_derives_formal_status_from_publication_event():
    correction = {
        "event_id": "publisher-correction-1",
        "source_version": "publisher-correction-v1",
        "source_type": "publisher_correction",
        "source_url": "https://publisher.example/article/correction",
        "observed_at": "2026-03-15",
        "status": "correction_published",
        "resolves_event_ids": ["observed-v1"],
    }

    result = reconcile_version_manifest(
        _manifest([_observed_event(), correction]),
        findings=[_finding()],
    )

    assert result.resolution_status is ResolutionStatus.FORMALLY_CORRECTED
    assert result.publisher_confirmation is True
    assert result.reconciled_findings[0]["open_for_scoring"] is False


def test_current_publisher_si_resolves_stale_version_without_formal_correction():
    current_si = {
        "event_id": "current-si-v2",
        "source_version": "si-v2",
        "source_type": "current_publisher_si",
        "source_url": "https://publisher.example/article/si-current",
        "observed_at": "2026-03-01",
        "status": "current_version_matches",
        "resolution_status": "resolved_by_version",
        "resolves_event_ids": ["observed-v1"],
        "supersedes_versions": ["si-v1"],
    }
    result = reconcile_version_manifest(
        _manifest([_observed_event(), current_si]),
        findings=[_finding()],
    )

    assert result.resolution_status is ResolutionStatus.RESOLVED_BY_VERSION
    assert result.publisher_confirmation is True
    assert result.open_medium_finding_count == 0
    reconciled = result.reconciled_findings[0]
    assert reconciled["resolution_status"] == "resolved_by_version"
    assert reconciled["open_for_scoring"] is False
    assert reconciled["historical"] is True


def test_unlinked_publisher_update_does_not_close_original_issue():
    unrelated_update = {
        "event_id": "publisher-update-other",
        "source_version": "article-v2",
        "source_type": "publisher_update",
        "source_url": "https://publisher.example/article/update",
        "observed_at": "2026-03-01",
        "status": "update_published",
        "resolution_status": "formally_corrected",
        "resolves_event_ids": ["different-observation"],
    }
    result = reconcile_version_manifest(
        _manifest([_observed_event(), unrelated_update]),
        findings=[_finding()],
    )

    assert result.resolution_status is ResolutionStatus.OPEN
    assert result.publisher_confirmation is False
    assert result.open_medium_finding_count == 1
    assert result.reconciled_findings[0]["open_for_scoring"] is True


def test_source_version_alone_cannot_link_an_unscoped_observation():
    observed = _observed_event()
    observed.pop("related_finding_ids")
    observed.pop("related_claim_ids")
    current_si = {
        "event_id": "current-si-v2",
        "source_version": "si-v2",
        "source_type": "current_publisher_si",
        "source_url": "https://publisher.example/article/si-current",
        "observed_at": "2026-03-01",
        "status": "current_version_matches",
        "resolution_status": "resolved_by_version",
        "resolves_event_ids": ["observed-v1"],
        "supersedes_versions": ["si-v1"],
    }
    finding = _finding()
    finding["provenance"].pop("version_event_id")
    finding["provenance"].pop("related_claim_ids")

    result = reconcile_version_manifest(
        _manifest([observed, current_si]),
        findings=[finding],
    )

    assert result.resolution_status is ResolutionStatus.OPEN
    assert result.reconciled_findings[0]["open_for_scoring"] is True


def test_version_manifest_rejects_private_paths_and_overclaiming_language():
    private_path = "C" + ":" + chr(92) + "Users" + chr(92) + "person" + chr(92) + "source.pdf"
    unsafe_event = _observed_event()
    unsafe_event["source_url"] = private_path
    unsafe_event["notes"] = "fraud " + "confirmed"

    with pytest.raises(ValidationError, match="unsafe public manifest content"):
        _manifest([unsafe_event])

    posix_event = _observed_event()
    posix_event["source_url"] = "/" + "home/person/source.pdf"
    with pytest.raises(ValidationError, match="unsafe public manifest content"):
        _manifest([posix_event])


def test_toy_version_manifest_loads_and_reconciles_offline():
    project_root = Path(__file__).resolve().parents[1]
    manifest_path = (
        project_root
        / "examples"
        / "toy_review_package"
        / "documents"
        / "version_manifest.yml"
    )

    manifest = load_version_manifest(manifest_path)
    toy_finding = _finding(source_version="publisher-v1")
    toy_finding["provenance"]["related_claim_ids"] = [
        "toy-concentration-main",
        "toy-concentration-si",
    ]
    result = reconcile_version_manifest(manifest, findings=[toy_finding])

    assert manifest.target_doi == "10.1000/toy-version"
    assert manifest.events[0].source_version == "publisher-v1"
    assert manifest.events[0].related_claim_ids == [
        "toy-concentration-main",
        "toy-concentration-si",
    ]
    assert result.resolution_status is ResolutionStatus.RESOLVED_BY_VERSION
    assert result.open_medium_finding_count == 0
    assert all(not Path(item["source_url"]).is_absolute() for item in result.timeline)


def test_active_rule_registry_adapter_executes_with_existing_detector_contract():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    rule = registry["publication_version_drift"]

    records = run_detector(
        rule,
        project_root / "examples" / "toy_review_package",
        options={"findings": [_finding()]},
    )

    assert len(records) == 1
    assert records[0].rule_id == "publication_version_drift"
    assert records[0].metadata["resolution_status"] == "resolved_by_version"
    assert records[0].metadata["open_for_scoring"] is False


def test_active_rule_adapter_blocks_unconfirmed_input_and_caps_risk():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    rule = registry["publication_version_drift"]
    package_dir = project_root / "examples" / "toy_review_package"

    unconfirmed = _finding()
    unconfirmed["human_confirmed"] = False
    assert run_detector(rule, package_dir, options={"findings": [unconfirmed]}) == []

    high = _finding()
    high["risk"] = "high"
    high["risk_level"] = "high"
    records = run_detector(rule, package_dir, options={"findings": [high]})
    assert len(records) == 1
    assert records[0].risk_level == "medium"
