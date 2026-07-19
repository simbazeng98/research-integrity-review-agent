from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from integrity_agent.core.evidence.ledger_schema import (
    BenignAlternative,
    EvidenceLocation,
    EvidenceRecord,
    ManualVerification,
    ReportLanguageGuard,
    RiskSignal,
    VerificationQuestion,
)
from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.core.safety import find_runtime_safety_issues


class ProcessStage(str, Enum):
    PREPARATION = "preparation"
    SONICATION = "sonication"
    VORTEX = "vortex"
    FILTRATION = "filtration"
    STORAGE = "storage"
    DLS = "dls"
    DEPOSITION = "deposition"


PROCESS_STAGE_ORDER = (
    ProcessStage.PREPARATION,
    ProcessStage.SONICATION,
    ProcessStage.VORTEX,
    ProcessStage.FILTRATION,
    ProcessStage.STORAGE,
    ProcessStage.DLS,
    ProcessStage.DEPOSITION,
)

_STAGE_RANK = {
    ProcessStage.PREPARATION: 0,
    ProcessStage.SONICATION: 1,
    ProcessStage.VORTEX: 1,
    ProcessStage.FILTRATION: 2,
    ProcessStage.STORAGE: 3,
    ProcessStage.DLS: 4,
    ProcessStage.DEPOSITION: 5,
}


class MeasurementStage(str, Enum):
    BEFORE_FILTRATION = "before_filtration"
    AFTER_FILTRATION = "after_filtration"
    UNKNOWN = "unknown"


class DistributionBasis(str, Enum):
    INTENSITY_WEIGHTED = "intensity_weighted"
    VOLUME_WEIGHTED = "volume_weighted"
    NUMBER_WEIGHTED = "number_weighted"
    Z_AVERAGE = "z_average"
    UNKNOWN = "unknown"


_MEASUREMENT_STAGE_ALIASES = {
    "pre_filtration": MeasurementStage.BEFORE_FILTRATION.value,
    "pre-filtration": MeasurementStage.BEFORE_FILTRATION.value,
    "before filtration": MeasurementStage.BEFORE_FILTRATION.value,
    "post_filtration": MeasurementStage.AFTER_FILTRATION.value,
    "post-filtration": MeasurementStage.AFTER_FILTRATION.value,
    "after filtration": MeasurementStage.AFTER_FILTRATION.value,
}

_DISTRIBUTION_BASIS_ALIASES = {
    "intensity": DistributionBasis.INTENSITY_WEIGHTED.value,
    "intensity-weighted": DistributionBasis.INTENSITY_WEIGHTED.value,
    "volume": DistributionBasis.VOLUME_WEIGHTED.value,
    "volume-weighted": DistributionBasis.VOLUME_WEIGHTED.value,
    "number": DistributionBasis.NUMBER_WEIGHTED.value,
    "number-weighted": DistributionBasis.NUMBER_WEIGHTED.value,
    "z-average": DistributionBasis.Z_AVERAGE.value,
    "z average": DistributionBasis.Z_AVERAGE.value,
}


class ProcessLineageRecord(BaseModel):
    """Human-curated sample-stage context for a DLS/filtration comparison."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    location: str = Field(min_length=1)
    stages: list[ProcessStage] = Field(default_factory=list)
    measurement_stage: MeasurementStage | None = None
    distribution_basis: DistributionBasis | None = None
    nominal_pore_nm: float | None = Field(default=None, gt=0)
    hydrodynamic_diameter_nm: float | None = Field(default=None, gt=0)
    notes: str | None = None
    human_confirmed: bool

    @model_validator(mode="before")
    @classmethod
    def normalize_compatible_fields(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        normalized = dict(data)
        aliases = {
            "dls_measurement_stage": "measurement_stage",
            "sample_stage": "measurement_stage",
            "dls_distribution_basis": "distribution_basis",
            "nominal_pore_size_nm": "nominal_pore_nm",
            "filter_pore_nm": "nominal_pore_nm",
            "dls_hydrodynamic_diameter_nm": "hydrodynamic_diameter_nm",
            "dls_diameter_nm": "hydrodynamic_diameter_nm",
        }
        for alias, canonical in aliases.items():
            if canonical not in normalized and alias in normalized:
                normalized[canonical] = normalized.pop(alias)

        measurement_stage = normalized.get("measurement_stage")
        if isinstance(measurement_stage, str):
            cleaned = measurement_stage.strip().lower()
            normalized["measurement_stage"] = _MEASUREMENT_STAGE_ALIASES.get(
                cleaned, cleaned
            )
        distribution_basis = normalized.get("distribution_basis")
        if isinstance(distribution_basis, str):
            cleaned = distribution_basis.strip().lower()
            normalized["distribution_basis"] = _DISTRIBUTION_BASIS_ALIASES.get(
                cleaned, cleaned.replace("-", "_").replace(" ", "_")
            )
        return normalized

    @field_validator("sample_id", "source_file", "location", mode="before")
    @classmethod
    def require_nonempty_string(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value.strip()

    @model_validator(mode="after")
    def validate_public_lineage_record(self) -> ProcessLineageRecord:
        ranks = [_STAGE_RANK[stage] for stage in self.stages]
        if ranks != sorted(ranks):
            raise ValueError("stages must follow the declared process-lineage order")
        if len(self.stages) != len(set(self.stages)):
            raise ValueError("stages must not contain duplicates")

        issues = find_runtime_safety_issues(self.model_dump(mode="json"))
        if issues:
            raise ValueError(
                "unsafe process-lineage content: " + "; ".join(sorted(set(issues)))
            )
        return self


_BENIGN_ALTERNATIVES = [
    "A filter's nominal pore rating can differ from its effective retention behavior.",
    "Soft or deformable particles can pass through a nominal pore smaller than a later hydrodynamic diameter.",
    "An intensity-weighted DLS distribution can emphasize rare larger aggregates.",
    "Aggregation can occur after filtration during storage, transport, or DLS sample handling.",
]


def _missing_context_fields(record: ProcessLineageRecord) -> list[str]:
    missing: list[str] = []
    if record.measurement_stage in {None, MeasurementStage.UNKNOWN}:
        missing.append("measurement_stage")
    if record.distribution_basis in {None, DistributionBasis.UNKNOWN}:
        missing.append("distribution_basis")
    if record.nominal_pore_nm is None:
        missing.append("nominal_pore_nm")
    if record.hydrodynamic_diameter_nm is None:
        missing.append("hydrodynamic_diameter_nm")
    return missing


def _common_provenance(record: ProcessLineageRecord) -> dict[str, Any]:
    return {
        "rule_id": "materials_sample_lineage",
        "sample_id": record.sample_id,
        "source_file": record.source_file,
        "location": record.location,
        "stages": [stage.value for stage in record.stages],
        "measurement_stage": (
            record.measurement_stage.value if record.measurement_stage else None
        ),
        "distribution_basis": (
            record.distribution_basis.value if record.distribution_basis else None
        ),
        "nominal_pore_nm": record.nominal_pore_nm,
        "hydrodynamic_diameter_nm": record.hydrodynamic_diameter_nm,
        "human_confirmed": record.human_confirmed,
        "open_for_scoring": False,
        "mrpi_eligible": False,
    }


def _missing_context_record(
    record: ProcessLineageRecord,
    *,
    finding_index: int,
    missing_context: list[str],
) -> EvidenceRecord:
    safe_language = (
        "Materials sample-lineage context is incomplete; no pore-size/DLS "
        "comparison was performed. Record the DLS aliquot stage, distribution "
        "basis, and relevant size values before review."
    )
    provenance = _common_provenance(record)
    provenance["missing_context"] = missing_context
    return EvidenceRecord(
        finding_id=f"MAT-LINEAGE-CONTEXT-{finding_index:03d}",
        finding_category="materials_sample_lineage",
        type="materials_sample_lineage_missing_context",
        title="Materials sample-lineage context is incomplete",
        summary=safe_language,
        safe_report_language=safe_language,
        risk="low",
        risk_level="low",
        needs_manual_review=True,
        evidence=[
            EvidenceLocation(
                source=record.source_file,
                location=record.location,
                metadata={"sample_id": record.sample_id},
            )
        ],
        manual_verification=ManualVerification(
            needed=True,
            requests=[
                "Record whether the DLS aliquot was taken before or after filtration.",
                "Record whether the reported DLS distribution is intensity-, volume-, number-weighted, or Z-average.",
            ],
        ),
        false_positive_risks=[
            "The missing stage or distribution basis may be documented outside the structured lineage record."
        ],
        alternative_explanations=[],
        limitations=[
            "No pore-size/DLS comparison is made while sample stage or distribution basis is unknown."
        ],
        provenance=provenance,
        rule_id="materials_sample_lineage",
        risk_signal=RiskSignal(
            risk_level="low",
            rule_id="materials_sample_lineage",
            workflow_id="materials_process_lineage",
            confidence=0.0,
        ),
        report_language_guard=ReportLanguageGuard(
            safe_report_language=safe_language,
            forbidden_verdict_phrases_blocked=True,
            requires_manual_verification_language=True,
        ),
        verification_questions=[
            VerificationQuestion(
                text="What sample stage and DLS distribution basis apply to this reported size?",
                evidence_location=record.location,
            )
        ],
        open_for_scoring=False,
        mrpi_eligible=False,
        signal_kind="missing_context",
    )


def _verification_question_record(
    record: ProcessLineageRecord,
    *,
    finding_index: int,
    diameter_to_pore_ratio: float,
    large_ratio_threshold: float,
) -> EvidenceRecord:
    safe_language = (
        "Materials sample-stage verification question: a reported post-filtration "
        "DLS hydrodynamic diameter is substantially larger than the nominal filter "
        "pore rating. Verify sample timing, filter behavior, distribution basis, "
        "and possible aggregation before interpreting the relationship."
    )
    provenance = _common_provenance(record)
    provenance.update(
        {
            "diameter_to_pore_ratio": diameter_to_pore_ratio,
            "large_ratio_threshold": large_ratio_threshold,
            "comparison_performed": True,
        }
    )
    return EvidenceRecord(
        finding_id=f"MAT-LINEAGE-QUESTION-{finding_index:03d}",
        finding_category="materials_sample_lineage",
        type="sample_stage_verification_question",
        title="Post-filtration DLS sample-stage question",
        summary=safe_language,
        safe_report_language=safe_language,
        risk="low",
        risk_level="low",
        needs_manual_review=True,
        evidence=[
            EvidenceLocation(
                source=record.source_file,
                location=record.location,
                metadata={
                    "sample_id": record.sample_id,
                    "nominal_pore_nm": record.nominal_pore_nm,
                    "hydrodynamic_diameter_nm": record.hydrodynamic_diameter_nm,
                    "distribution_basis": record.distribution_basis.value,
                },
            )
        ],
        manual_verification=ManualVerification(
            needed=True,
            requests=[
                "Confirm that the DLS aliquot was taken after the stated filtration step.",
                "Verify the filter material, nominal pore rating, and effective retention context.",
                "Inspect the full DLS distribution and whether it is intensity-, volume-, number-weighted, or Z-average.",
                "Check storage time and handling between filtration and DLS measurement.",
            ],
        ),
        false_positive_risks=list(_BENIGN_ALTERNATIVES),
        alternative_explanations=list(_BENIGN_ALTERNATIVES),
        limitations=[
            "Nominal filter ratings and DLS hydrodynamic distributions do not describe identical measurement constructs.",
            "The structured record does not establish particle rigidity, filter retention efficiency, or aggregation kinetics.",
        ],
        provenance=provenance,
        rule_id="materials_sample_lineage",
        risk_signal=RiskSignal(
            risk_level="low",
            rule_id="materials_sample_lineage",
            workflow_id="materials_process_lineage",
            confidence=0.5,
        ),
        report_language_guard=ReportLanguageGuard(
            safe_report_language=safe_language,
            forbidden_verdict_phrases_blocked=True,
            requires_manual_verification_language=True,
        ),
        verification_questions=[
            VerificationQuestion(
                text="Do the filter and DLS values refer to the same post-filtration aliquot and distribution basis?",
                evidence_location=record.location,
            )
        ],
        benign_alternatives=[
            BenignAlternative(text=alternative) for alternative in _BENIGN_ALTERNATIVES
        ],
        open_for_scoring=False,
        mrpi_eligible=False,
        signal_kind="verification_question",
        correlation_group=f"materials_sample_lineage:{record.sample_id}",
    )


def run_materials_process_lineage_check(
    records: Iterable[ProcessLineageRecord | Mapping[str, Any]],
    *,
    large_ratio_threshold: float = 3.0,
) -> list[EvidenceRecord]:
    """Create conservative questions from human-curated process-lineage records."""

    if large_ratio_threshold <= 1.0:
        raise ValueError("large_ratio_threshold must be greater than 1")

    findings: list[EvidenceRecord] = []
    for raw_record in records:
        record = (
            raw_record
            if isinstance(raw_record, ProcessLineageRecord)
            else ProcessLineageRecord.model_validate(raw_record)
        )
        if not record.human_confirmed:
            continue
        missing_context = _missing_context_fields(record)
        if missing_context:
            findings.append(
                _missing_context_record(
                    record,
                    finding_index=len(findings) + 1,
                    missing_context=missing_context,
                )
            )
            continue

        # Known pre-filtration measurements do not support a post-filtration
        # pore-size comparison and therefore create no question.
        if record.measurement_stage is not MeasurementStage.AFTER_FILTRATION:
            continue

        diameter_to_pore_ratio = (
            record.hydrodynamic_diameter_nm / record.nominal_pore_nm
        )
        if diameter_to_pore_ratio < large_ratio_threshold:
            continue

        findings.append(
            _verification_question_record(
                record,
                finding_index=len(findings) + 1,
                diameter_to_pore_ratio=diameter_to_pore_ratio,
                large_ratio_threshold=large_ratio_threshold,
            )
        )

    output_issues = find_runtime_safety_issues(
        [finding.model_dump(mode="json") for finding in findings]
    )
    if output_issues:
        raise ValueError(
            "unsafe process-lineage output: "
            + "; ".join(sorted(set(output_issues)))
        )
    return findings


def run_materials_process_lineage_detector(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    """Adapter for the existing function-detector registry contract.

    Records must be supplied explicitly. The adapter does not infer lineage from
    filenames, PDFs, or free text.
    """

    del package_dir
    options = options or {}
    records = options.get("records") or []
    if not records:
        return []
    threshold = float(options.get("large_ratio_threshold", 3.0))
    evidence_records = run_materials_process_lineage_check(
        records,
        large_ratio_threshold=threshold,
    )

    results: list[RuleExecutionResult] = []
    for finding in evidence_records:
        metadata = dict(finding.provenance)
        metadata.update(
            {
                "finding_type": finding.type,
                "open_for_scoring": finding.open_for_scoring,
                "mrpi_eligible": finding.mrpi_eligible,
                "signal_kind": finding.signal_kind,
            }
        )
        results.append(
            RuleExecutionResult(
                finding_id=finding.finding_id,
                rule_id=rule.rule_id,
                risk_level=finding.risk_level,
                evidence_items=[item.model_dump(mode="json") for item in finding.evidence],
                manual_verification=finding.manual_verification.model_dump(mode="json"),
                false_positive_risks=[str(item) for item in finding.false_positive_risks],
                safe_report_language=str(finding.safe_report_language),
                alternative_explanations=[
                    str(item) for item in finding.alternative_explanations
                ],
                suggested_verification_questions=[
                    str(question.text) for question in finding.verification_questions
                ],
                limitations=[str(item) for item in finding.limitations],
                metadata=metadata,
            )
        )
    return results


__all__ = [
    "DistributionBasis",
    "MeasurementStage",
    "PROCESS_STAGE_ORDER",
    "ProcessLineageRecord",
    "ProcessStage",
    "run_materials_process_lineage_check",
    "run_materials_process_lineage_detector",
]
