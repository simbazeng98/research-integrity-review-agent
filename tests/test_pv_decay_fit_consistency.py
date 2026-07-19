from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from integrity_agent.core.claims.version_schema import VersionManifest
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.registry import run_detector
from integrity_agent.domains.photovoltaics.decay_fit_consistency import (
    AverageLifetimeFormula,
    DecayComponent,
    DecayFitRecord,
    compute_average_lifetime,
    normalize_decay_time,
    run_decay_fit_consistency_check,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file
from integrity_agent.workflows.version_reconciliation import reconcile_version_manifest
from integrity_agent.workflows.pv_domain_review import (
    PVDecayFitReviewError,
    run_pv_decay_fit_review,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _components() -> list[dict]:
    return [
        {"amplitude": 1.0, "lifetime": 1.0, "unit": "us"},
        {"amplitude": 3.0, "lifetime": 2.0, "unit": "μs"},
    ]


def _record(**overrides) -> dict:
    record = {
        "record_id": "claim-figure-trpl",
        "claim_id": "claim-figure-trpl",
        "decay_type": "trpl",
        "sample_id": "sample-A",
        "source_version": "si-v1",
        "source_document": "figure_annotation",
        "source": "documents/claims.jsonl",
        "location": "Figure 2 annotation",
        "source_hash": "sha256:toy-figure",
        "reported_average": 1.75,
        "reported_unit": "μs",
        "declared_formula": "amplitude_weighted",
        "components": _components(),
        "human_confirmed": True,
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    ("value", "unit", "expected_ns"),
    [
        (1250, "ns", 1250.0),
        (1.25, "us", 1250.0),
        (1.25, "μs", 1250.0),
        (1.25, "µs", 1250.0),
        (0.00125, "ms", 1250.0),
    ],
)
def test_decay_time_unit_normalization(value, unit, expected_ns):
    assert normalize_decay_time(value, unit, target_unit="ns") == pytest.approx(expected_ns)


def test_decay_time_rejects_unknown_unit():
    with pytest.raises(ValueError, match="unit"):
        normalize_decay_time(1, "minutes")


def test_biexponential_average_supports_both_declared_conventions():
    components = [DecayComponent.model_validate(item) for item in _components()]

    amplitude_weighted = compute_average_lifetime(
        components,
        AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
        output_unit="ns",
    )
    intensity_weighted = compute_average_lifetime(
        components,
        AverageLifetimeFormula.INTENSITY_WEIGHTED,
        output_unit="ns",
    )

    assert amplitude_weighted == pytest.approx(1750.0)
    assert intensity_weighted == pytest.approx(13_000_000 / 7_000)
    assert intensity_weighted != pytest.approx(amplitude_weighted)


@pytest.mark.parametrize(
    ("formula", "expected_ns"),
    [
        ("ΣAiτi/ΣAi", 1750.0),
        ("ΣAiτi²/ΣAiτi", 13_000_000 / 7_000),
    ],
)
def test_formula_symbols_from_the_public_contract_are_supported(formula, expected_ns):
    assert compute_average_lifetime(
        _components(),
        formula,
        output_unit="ns",
    ) == pytest.approx(expected_ns)


def test_correct_declared_formula_and_unit_conversion_do_not_emit_finding():
    records = [DecayFitRecord.model_validate(_record())]

    assert run_decay_fit_consistency_check(records) == []


def test_wrong_figure_value_against_same_sample_version_source_params_is_medium_traceable():
    figure = _record(
        reported_average=2.4,
        reported_unit="us",
        components=[],
    )
    source_params = _record(
        record_id="claim-source-params",
        claim_id="claim-source-params",
        source_document="source_parameters",
        source="source_data/trpl_fit.csv",
        location="rows 2-3",
        source_hash="sha256:toy-source-params",
        reported_average=None,
        reported_unit=None,
        declared_formula=None,
        components=_components(),
    )

    findings = run_decay_fit_consistency_check([figure, source_params])

    assert len(findings) == 1
    record = findings[0].to_ledger_record()
    assert record["type"] == "decay_fit_value_mismatch"
    assert record["risk_level"] == "medium"
    assert record["provenance"]["open_for_scoring"] is True
    assert record["provenance"]["mrpi_eligible"] is True
    assert record["provenance"]["source_version"] == "si-v1"
    assert record["provenance"]["sample_id"] == "sample-A"
    assert record["provenance"]["related_claim_ids"] == [
        "claim-figure-trpl",
        "claim-source-params",
    ]
    assert record["provenance"]["declared_formula"] == "amplitude_weighted"
    assert record["provenance"]["reported_average_ns"] == pytest.approx(2400.0)
    assert record["provenance"]["recomputed_average_ns"] == pytest.approx(1750.0)
    assert len(record["evidence"]) == 2
    assert {
        (
            item["metadata"]["source_document"],
            item["metadata"]["source_version"],
            item["metadata"]["claim_id"],
        )
        for item in record["evidence"]
    } == {
        ("figure_annotation", "si-v1", "claim-figure-trpl"),
        ("source_parameters", "si-v1", "claim-source-params"),
    }
    assert "candidate" in str(record["safe_report_language"]).lower()


def test_two_valid_average_conventions_are_not_cross_compared_as_mismatch():
    amplitude = _record(
        record_id="claim-table-amplitude",
        claim_id="claim-table-amplitude",
        source_document="fit_table",
        location="Table S4 amplitude-weighted column",
        declared_formula="amplitude_weighted",
        reported_average=1.75,
        reported_unit="us",
    )
    intensity = _record(
        record_id="claim-figure-intensity",
        claim_id="claim-figure-intensity",
        source_document="figure_annotation",
        location="Figure S8 intensity-weighted annotation",
        declared_formula="intensity_weighted",
        reported_average=13_000_000 / 7_000,
        reported_unit="ns",
    )

    assert run_decay_fit_consistency_check([amplitude, intensity]) == []


def test_undeclared_formula_is_low_ambiguity_and_not_open_for_scoring():
    findings = run_decay_fit_consistency_check(
        [_record(declared_formula=None, reported_average=1.75, reported_unit="us")]
    )

    assert len(findings) == 1
    record = findings[0].to_ledger_record()
    assert record["type"] == "decay_fit_formula_ambiguity"
    assert record["risk_level"] == "low"
    assert record["provenance"]["open_for_scoring"] is False
    assert record["provenance"]["mrpi_eligible"] is False
    assert record["provenance"]["declared_formula"] is None
    assert "formula" in str(record["safe_report_language"]).lower()


def test_different_sample_or_version_parameters_never_create_medium_mismatch():
    report = _record(components=[], reported_average=2.4)
    other_sample = _record(
        record_id="other-sample",
        claim_id="other-sample",
        sample_id="sample-B",
        source_document="source_parameters",
        reported_average=None,
        reported_unit=None,
        declared_formula=None,
        components=_components(),
    )
    other_version = _record(
        record_id="other-version",
        claim_id="other-version",
        source_version="si-v2",
        source_document="source_parameters",
        reported_average=None,
        reported_unit=None,
        declared_formula=None,
        components=_components(),
    )

    findings = run_decay_fit_consistency_check([report, other_sample, other_version])

    assert all(finding.risk.value == "low" for finding in findings)
    assert all(finding.provenance["open_for_scoring"] is False for finding in findings)


def test_unconfirmed_decay_records_never_create_findings():
    assert run_decay_fit_consistency_check(
        [_record(human_confirmed=False, reported_average=9.9)]
    ) == []


def test_decay_record_requires_explicit_human_confirmation():
    record = _record()
    del record["human_confirmed"]

    with pytest.raises(ValidationError, match="human_confirmed"):
        DecayFitRecord.model_validate(record)


def test_decay_findings_validate_as_ledger_and_can_be_resolved_by_version(tmp_path):
    findings = run_decay_fit_consistency_check([_record(reported_average=2.4)])
    ledger_path = tmp_path / "decay_findings.jsonl"
    ledger_path.write_text(findings[0].to_json_line() + "\n", encoding="utf-8")
    validation = validate_ledger_file(ledger_path)
    assert validation.ok, [issue.format() for issue in validation.issues]

    finding_record = findings[0].to_ledger_record()
    manifest = VersionManifest.model_validate(
        {
            "target_doi": "10.1000/toy-decay",
            "events": [
                {
                    "event_id": "observed-si-v1",
                    "source_version": "si-v1",
                    "source_type": "original_public_version",
                    "source_url": "https://publisher.example/toy/si-v1",
                    "observed_at": "2026-01-01",
                    "status": "mismatch_observed",
                    "related_finding_ids": [finding_record["finding_id"]],
                    "related_claim_ids": finding_record["provenance"]["related_claim_ids"],
                },
                {
                    "event_id": "current-si-v2",
                    "source_version": "si-v2",
                    "source_type": "current_publisher_si",
                    "source_url": "https://publisher.example/toy/si-current",
                    "observed_at": "2026-02-01",
                    "status": "current_version_matches",
                    "resolution_status": "resolved_by_version",
                    "resolves_event_ids": ["observed-si-v1"],
                    "supersedes_versions": ["si-v1"],
                },
            ],
        }
    )
    reconciled = reconcile_version_manifest(manifest, findings=[finding_record])

    assert reconciled.reconciled_findings[0]["historical"] is True
    assert reconciled.reconciled_findings[0]["open_for_scoring"] is False


def test_rule_registry_adapter_is_active_offline_and_medium_capped(tmp_path):
    registry = load_rule_registry(
        _project_root() / "knowledge_base" / "detector_rules"
    )
    rule = registry["pv_decay_fit_consistency"]

    assert rule.status == "active"
    assert rule.runtime_status == "active"
    assert rule.execution_mode == "offline"
    assert rule.risk_ceiling == "medium"
    assert rule.detector_module == (
        "integrity_agent.domains.photovoltaics.decay_fit_consistency"
    )
    assert rule.detector_function == "detect_pv_decay_fit_consistency"

    results = run_detector(
        rule,
        _project_root(),
        options={"records": [_record(reported_average=2.4)]},
    )
    assert len(results) == 1
    assert results[0].risk_level == "medium"

    ledger_path = tmp_path / "adapter.jsonl"
    ledger_path.write_text(
        "".join(json.dumps(item.to_record()) + "\n" for item in results),
        encoding="utf-8",
    )
    assert validate_ledger_file(ledger_path).ok


def test_detector_without_structured_records_does_not_extract_documents():
    registry = load_rule_registry(
        _project_root() / "knowledge_base" / "detector_rules"
    )
    rule = registry["pv_decay_fit_consistency"]

    assert run_detector(rule, _project_root(), options={}) == []


def _write_records(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_pv_decay_fit_review_wrapper_writes_validator_clean_ledger_and_summary(tmp_path):
    records_path = tmp_path / "decay_records.jsonl"
    _write_records(records_path, [_record(reported_average=2.4)])

    findings_path, summary_path = run_pv_decay_fit_review(
        records_path,
        output_dir=tmp_path / "review",
    )

    validation = validate_ledger_file(findings_path)
    assert validation.ok, [issue.format() for issue in validation.issues]
    assert validation.records == 1
    finding = json.loads(findings_path.read_text(encoding="utf-8"))
    assert finding["rule_id"] == "pv_decay_fit_consistency"
    assert finding["provenance"]["source_version"] == "si-v1"
    summary = summary_path.read_text(encoding="utf-8")
    assert "Status: success" in summary
    assert "Input records: 1" in summary
    assert "Findings: 1" in summary
    assert "PDF" in summary
    assert str(tmp_path) not in summary


def test_pv_decay_fit_review_empty_file_is_distinct_warning_with_empty_ledger(tmp_path):
    records_path = tmp_path / "decay_records.jsonl"
    records_path.write_text("", encoding="utf-8")

    findings_path, summary_path = run_pv_decay_fit_review(
        records_path,
        output_dir=tmp_path / "review",
    )

    assert findings_path.read_text(encoding="utf-8") == ""
    assert validate_ledger_file(findings_path).ok
    summary = summary_path.read_text(encoding="utf-8")
    assert "Status: warning" in summary
    assert "Input records: 0" in summary
    assert "No structured decay-fit records" in summary


def test_pv_decay_fit_review_parse_failure_is_nonzero_and_removes_stale_outputs(tmp_path):
    output_dir = tmp_path / "review"
    valid_path = tmp_path / "valid.jsonl"
    _write_records(valid_path, [_record(reported_average=2.4)])
    stale_findings, stale_summary = run_pv_decay_fit_review(valid_path, output_dir=output_dir)
    assert stale_findings.exists() and stale_summary.exists()

    invalid_path = tmp_path / "invalid.jsonl"
    invalid_path.write_text('{"record_id": ', encoding="utf-8")

    with pytest.raises(PVDecayFitReviewError, match="line 1"):
        run_pv_decay_fit_review(invalid_path, output_dir=output_dir)

    assert not stale_findings.exists()
    assert not stale_summary.exists()


def test_pv_decay_fit_review_refuses_pdf_or_unstructured_input(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-toy")

    with pytest.raises(PVDecayFitReviewError, match="JSONL"):
        run_pv_decay_fit_review(pdf_path, output_dir=tmp_path / "review")

    assert not (tmp_path / "review" / "pv_decay_fit_findings.jsonl").exists()


def test_pv_decay_fit_review_never_deletes_an_input_that_matches_output_name(tmp_path):
    output_dir = tmp_path / "review"
    input_path = output_dir / "pv_decay_fit_findings.jsonl"
    _write_records(input_path, [_record(reported_average=2.4)])

    with pytest.raises(PVDecayFitReviewError, match="must differ"):
        run_pv_decay_fit_review(input_path, output_dir=output_dir)

    assert input_path.exists()
    assert "claim-figure-trpl" in input_path.read_text(encoding="utf-8")
