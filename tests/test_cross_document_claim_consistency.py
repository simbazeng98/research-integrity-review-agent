from __future__ import annotations

import json
from pathlib import Path

from integrity_agent.core.claims import AtomicClaim
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.claims.cross_document import (
    compare_cross_document_claims,
)
from integrity_agent.detectors.registry import run_detector
from integrity_agent.workflows.cross_document_review import run_cross_document_review
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _claim(**overrides) -> dict:
    record = {
        "claim_id": "claim-main-1",
        "claim_type": "concentration",
        "value": "2",
        "unit": "mg/mL",
        "device_variant": "wide-bandgap",
        "sample_id": "device-A",
        "measurement_context": "precursor preparation",
        "source_document": "main",
        "source_version": "publisher-v1",
        "location": "Page 4, Methods, paragraph 2",
        "source_hash": "sha256:toy-main-hash",
        "human_confirmed": True,
    }
    record.update(overrides)
    return record


def _pair(**second_overrides) -> list[AtomicClaim]:
    second = {
        "claim_id": "claim-si-1",
        "value": "3",
        "source_document": "si",
        "location": "SI Page 7, section S2",
        "source_hash": "sha256:toy-si-hash",
    }
    second.update(second_overrides)
    return [
        AtomicClaim.model_validate(_claim()),
        AtomicClaim.model_validate(_claim(**second)),
    ]


def test_same_context_numeric_mismatch_is_medium_traceable_visible_issue():
    findings = compare_cross_document_claims(_pair())

    assert len(findings) == 1
    record = findings[0].to_ledger_record()
    assert record["type"] == "visible_consistency_issue"
    assert record["risk_level"] == "medium"
    assert record["provenance"]["open_for_scoring"] is True
    assert record["provenance"]["comparison_key"] == {
        "claim_type": "concentration",
        "device_variant": "wide-bandgap",
        "sample_id": "device-A",
        "measurement_context": "precursor preparation",
        "source_version": "publisher-v1",
    }
    assert record["provenance"]["logical_context_key"] == {
        "claim_type": "concentration",
        "device_variant": "wide-bandgap",
        "sample_id": "device-A",
        "measurement_context": "precursor preparation",
    }
    assert record["provenance"]["related_claim_ids"] == [
        "claim-main-1",
        "claim-si-1",
    ]
    assert len(record["evidence"]) == 2
    assert {
        (
            item["metadata"]["source_document"],
            item["metadata"]["source_version"],
            item["metadata"]["source_hash"],
        )
        for item in record["evidence"]
    } == {
        ("main", "publisher-v1", "sha256:toy-main-hash"),
        ("si", "publisher-v1", "sha256:toy-si-hash"),
    }
    assert "visible consistency issue" in str(record["safe_report_language"]).lower()
    alternatives = " ".join(str(item) for item in record["alternative_explanations"]).lower()
    for expected in ("variant", "typographical", "stale", "unit conversion"):
        assert expected in alternatives


def test_unconfirmed_or_different_variant_claims_never_create_a_finding():
    unconfirmed = _pair(human_confirmed=False)
    assert compare_cross_document_claims(unconfirmed) == []

    different_variant = _pair(device_variant="narrow-bandgap")
    assert compare_cross_document_claims(different_variant) == []

    different_version = _pair(source_version="publisher-v2")
    assert compare_cross_document_claims(different_version) == []


def test_decimal_whitelist_unit_normalization_avoids_false_mismatch():
    claims = [
        AtomicClaim.model_validate(
            _claim(
                claim_type="trpl_fit",
                value="1.1702",
                unit="μs",
                measurement_context="TRPL biexponential fit",
            )
        ),
        AtomicClaim.model_validate(
            _claim(
                claim_id="claim-si-trpl",
                claim_type="trpl_fit",
                value="1170.2",
                unit="ns",
                measurement_context="TRPL biexponential fit",
                source_document="si",
                location="SI Page 9, Table S4",
                source_hash="sha256:toy-si-trpl-hash",
            )
        ),
    ]

    assert compare_cross_document_claims(claims) == []


def test_layer_order_change_with_same_multiset_is_a_visible_issue():
    findings = compare_cross_document_claims(
        [
            AtomicClaim.model_validate(
                _claim(
                    claim_id="claim-main-layer",
                    claim_type="layer_order",
                    value="ITO / SnO2 / perovskite / Au",
                    unit="unitless",
                    measurement_context="device stack",
                )
            ),
            AtomicClaim.model_validate(
                _claim(
                    claim_id="claim-si-layer",
                    claim_type="layer_order",
                    value="ITO / perovskite / SnO2 / Au",
                    unit="unitless",
                    measurement_context="device stack",
                    source_document="si",
                    location="SI Page 2, device architecture",
                    source_hash="sha256:toy-si-layer-hash",
                )
            ),
        ]
    )

    assert len(findings) == 1
    assert findings[0].provenance["comparison_kind"] == "layer_order_change"


def test_explicit_reversed_iodide_bromide_ratio_is_a_visible_issue():
    claims = [
        AtomicClaim.model_validate(
            _claim(
                claim_id="claim-main-composition",
                claim_type="composition",
                value="I:Br = 3:1",
                unit="unitless",
                measurement_context="perovskite composition",
            )
        ),
        AtomicClaim.model_validate(
            _claim(
                claim_id="claim-si-composition",
                claim_type="composition",
                value="I:Br = 1:3",
                unit="unitless",
                measurement_context="perovskite composition",
                source_document="si",
                location="SI Page 3, composition table",
                source_hash="sha256:toy-si-composition-hash",
            )
        ),
    ]

    findings = compare_cross_document_claims(claims)

    assert len(findings) == 1
    assert findings[0].provenance["comparison_kind"] == "composition_ratio_change"


def test_missing_context_or_unknown_unit_is_low_question_not_open_score():
    missing_context = _pair(sample_id=None)
    missing_findings = compare_cross_document_claims(missing_context)
    assert len(missing_findings) == 1
    missing_record = missing_findings[0].to_ledger_record()
    assert missing_record["risk_level"] == "low"
    assert missing_record["type"] == "cross_document_verification_question"
    assert missing_record["provenance"]["open_for_scoring"] is False

    unknown_unit_claims = [
        _claim(unit="mg per unknown volume"),
        _claim(
            claim_id="claim-si-unknown-unit",
            value="3",
            unit="mg per unknown volume",
            source_document="si",
            location="SI Page 7, section S2",
            source_hash="sha256:toy-si-unknown-unit-hash",
        ),
    ]
    unknown_findings = compare_cross_document_claims(unknown_unit_claims)
    assert len(unknown_findings) == 1
    unknown_record = unknown_findings[0].to_ledger_record()
    assert unknown_record["risk_level"] == "low"
    assert unknown_record["provenance"]["open_for_scoring"] is False
    assert unknown_record["provenance"]["comparison_kind"] == "unit_review_question"


def test_workflow_writes_a_validator_clean_ledger_and_registry_adapter_runs(
    tmp_path: Path,
):
    project_root = Path(__file__).resolve().parents[1]
    claims_path = tmp_path / "claims.jsonl"
    claims_path.write_text(
        "".join(json.dumps(item) + "\n" for item in [_claim(), _claim(
            claim_id="claim-si-1",
            value="3",
            source_document="si",
            location="SI Page 7, section S2",
            source_hash="sha256:toy-si-hash",
        )]),
        encoding="utf-8",
    )

    ledger_path, summary_path = run_cross_document_review(
        claims_path,
        output_dir=tmp_path / "review",
    )

    validation = validate_ledger_file(ledger_path)
    assert validation.ok, [issue.format() for issue in validation.issues]
    assert validation.records == 1
    assert summary_path.exists()

    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    rule = registry["cross_document_claim_consistency"]
    records = run_detector(
        rule,
        project_root,
        options={"claims": [_claim(), _claim(
            claim_id="claim-si-1",
            value="3",
            source_document="si",
            location="SI Page 7, section S2",
            source_hash="sha256:toy-si-hash",
        )]},
    )
    assert len(records) == 1
    assert records[0].rule_id == "cross_document_claim_consistency"
    assert records[0].risk_level == "medium"
    assert records[0].metadata["logical_context_key"] == {
        "claim_type": "concentration",
        "device_variant": "wide-bandgap",
        "sample_id": "device-A",
        "measurement_context": "precursor preparation",
    }
