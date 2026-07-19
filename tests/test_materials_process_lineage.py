from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.core.safety import FORBIDDEN_VERDICT_PHRASES
from integrity_agent.detectors.registry import run_detector
from integrity_agent.domains.materials_characterization.process_lineage import (
    PROCESS_STAGE_ORDER,
    DistributionBasis,
    MeasurementStage,
    ProcessLineageRecord,
    ProcessStage,
    run_materials_process_lineage_check,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _record(**overrides) -> ProcessLineageRecord:
    data = {
        "sample_id": "toy-dispersion-01",
        "source_file": "materials/toy_process_lineage.yml",
        "location": "sample lineage row 1",
        "stages": [
            "preparation",
            "sonication",
            "filtration",
            "storage",
            "dls",
            "deposition",
        ],
        "measurement_stage": "after_filtration",
        "distribution_basis": "intensity_weighted",
        "nominal_pore_nm": 220.0,
        "hydrodynamic_diameter_nm": 1000.0,
        "human_confirmed": True,
    }
    data.update(overrides)
    return ProcessLineageRecord.model_validate(data)


def test_process_lineage_requires_explicit_human_confirmation():
    data = _record().model_dump(mode="json")
    data.pop("human_confirmed")

    with pytest.raises(ValidationError, match="human_confirmed"):
        ProcessLineageRecord.model_validate(data)


def test_unconfirmed_process_lineage_records_never_create_findings():
    assert run_materials_process_lineage_check(
        [_record(human_confirmed=False)]
    ) == []


def test_process_stage_model_preserves_declared_lineage_order():
    assert PROCESS_STAGE_ORDER == (
        ProcessStage.PREPARATION,
        ProcessStage.SONICATION,
        ProcessStage.VORTEX,
        ProcessStage.FILTRATION,
        ProcessStage.STORAGE,
        ProcessStage.DLS,
        ProcessStage.DEPOSITION,
    )


def test_post_filtration_large_dls_size_creates_low_non_scoring_question(tmp_path: Path):
    findings = run_materials_process_lineage_check([_record()])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.type == "sample_stage_verification_question"
    assert finding.risk_level == "low"
    assert finding.open_for_scoring is False
    assert finding.mrpi_eligible is False
    assert finding.needs_manual_review is True
    assert finding.provenance["measurement_stage"] == "after_filtration"
    assert finding.provenance["distribution_basis"] == "intensity_weighted"
    assert finding.provenance["diameter_to_pore_ratio"] == 1000.0 / 220.0
    assert finding.evidence[0].source == "materials/toy_process_lineage.yml"
    assert finding.evidence[0].location == "sample lineage row 1"

    ledger_path = tmp_path / "materials_lineage.jsonl"
    ledger_path.write_text(finding.model_dump_json() + "\n", encoding="utf-8")
    assert validate_ledger_file(ledger_path).ok


def test_lineage_question_lists_required_benign_alternatives_and_safe_language():
    finding = run_materials_process_lineage_check([_record()])[0]
    alternatives = " ".join(str(item) for item in finding.alternative_explanations).lower()
    rendered = json.dumps(finding.model_dump(mode="json"), ensure_ascii=False).lower()

    assert "nominal" in alternatives and "effective" in alternatives
    assert "soft" in alternatives and "deformable" in alternatives
    assert "intensity-weighted" in alternatives and "rare" in alternatives
    assert "after filtration" in alternatives and "aggregation" in alternatives
    assert ("physically " + "impossible") not in rendered
    for phrase in FORBIDDEN_VERDICT_PHRASES:
        assert phrase.lower() not in rendered


def test_unknown_measurement_stage_yields_missing_context_without_size_comparison():
    finding = run_materials_process_lineage_check(
        [_record(measurement_stage="unknown")]
    )[0]

    assert finding.type == "materials_sample_lineage_missing_context"
    assert finding.open_for_scoring is False
    assert finding.mrpi_eligible is False
    assert "measurement_stage" in finding.provenance["missing_context"]
    assert "diameter_to_pore_ratio" not in finding.provenance
    assert "no pore-size/dls comparison was performed" in finding.safe_report_language.lower()


def test_unknown_distribution_basis_yields_missing_context_only():
    finding = run_materials_process_lineage_check(
        [_record(distribution_basis="unknown")]
    )[0]

    assert finding.type == "materials_sample_lineage_missing_context"
    assert finding.risk_level == "low"
    assert "distribution_basis" in finding.provenance["missing_context"]
    assert "diameter_to_pore_ratio" not in finding.provenance


def test_pre_filtration_or_not_substantially_larger_dls_values_do_not_trigger():
    before_filtration = _record(measurement_stage="before_filtration")
    comparable_size = _record(
        distribution_basis="number_weighted",
        hydrodynamic_diameter_nm=440.0,
    )

    assert run_materials_process_lineage_check([before_filtration]) == []
    assert run_materials_process_lineage_check([comparable_size]) == []


def test_schema_normalizes_common_stage_and_distribution_aliases():
    record = _record(
        measurement_stage="post-filtration",
        distribution_basis="intensity",
    )

    assert record.measurement_stage is MeasurementStage.AFTER_FILTRATION
    assert record.distribution_basis is DistributionBasis.INTENSITY_WEIGHTED


def test_active_rule_adapter_uses_structured_records_only():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    rule = registry["materials_sample_lineage"]

    findings = run_detector(
        rule,
        project_root,
        options={"records": [_record().model_dump(mode="json")]},
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "materials_sample_lineage"
    assert findings[0].risk_level == "low"
    assert findings[0].metadata["open_for_scoring"] is False
    assert findings[0].metadata["mrpi_eligible"] is False
