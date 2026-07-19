from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)
from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.core.safety import find_runtime_safety_issues


RULE_ID = "pv_decay_fit_consistency"
DEFAULT_RELATIVE_TOLERANCE = 0.02
DEFAULT_ABSOLUTE_TOLERANCE_NS = 0.5


class AverageLifetimeFormula(str, Enum):
    AMPLITUDE_WEIGHTED = "amplitude_weighted"
    INTENSITY_WEIGHTED = "intensity_weighted"


_FORMULA_ALIASES = {
    "amplitude_weighted": AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
    "amplitude-weighted": AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
    "amplitude weighted": AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
    "sum_ai_tau_i_over_sum_ai": AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
    "σaiτi/σai": AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
    "∑aiτi/∑ai": AverageLifetimeFormula.AMPLITUDE_WEIGHTED,
    "intensity_weighted": AverageLifetimeFormula.INTENSITY_WEIGHTED,
    "intensity-weighted": AverageLifetimeFormula.INTENSITY_WEIGHTED,
    "intensity weighted": AverageLifetimeFormula.INTENSITY_WEIGHTED,
    "sum_ai_tau_i_squared_over_sum_ai_tau_i": AverageLifetimeFormula.INTENSITY_WEIGHTED,
    "σaiτi²/σaiτi": AverageLifetimeFormula.INTENSITY_WEIGHTED,
    "∑aiτi²/∑aiτi": AverageLifetimeFormula.INTENSITY_WEIGHTED,
}

_UNIT_TO_NS = {
    "ns": Decimal("1"),
    "us": Decimal("1000"),
    "µs": Decimal("1000"),
    "ms": Decimal("1000000"),
}


def _unit_key(unit: str) -> str:
    return unit.strip().replace("μ", "µ").lower()


def _finite_decimal(value: Any, *, field_name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite positive number")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite positive number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field_name} must be a finite positive number")
    return parsed


def normalize_decay_time(
    value: Any,
    unit: str,
    *,
    target_unit: str = "ns",
) -> float:
    """Convert a positive decay lifetime among ns, us/μs, and ms."""
    source_key = _unit_key(unit)
    target_key = _unit_key(target_unit)
    if source_key not in _UNIT_TO_NS:
        raise ValueError(f"unsupported decay-time unit: {unit!r}")
    if target_key not in _UNIT_TO_NS:
        raise ValueError(f"unsupported target decay-time unit: {target_unit!r}")
    numeric = _finite_decimal(value, field_name="decay time")
    value_ns = numeric * _UNIT_TO_NS[source_key]
    return float(value_ns / _UNIT_TO_NS[target_key])


normalize_lifetime_to_ns = normalize_decay_time


def resolve_average_formula(value: Any) -> AverageLifetimeFormula | None:
    if isinstance(value, AverageLifetimeFormula):
        return value
    if value is None:
        return None
    key = " ".join(str(value).strip().split()).lower()
    return _FORMULA_ALIASES.get(key)


class DecayComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amplitude: float = Field(ge=0)
    lifetime: float = Field(gt=0)
    unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unit_and_numbers(self) -> DecayComponent:
        _finite_decimal(self.amplitude, field_name="amplitude") if self.amplitude else Decimal("0")
        normalize_decay_time(self.lifetime, self.unit)
        return self


class DecayFitRecord(BaseModel):
    """Human-confirmed structured decay-fit observation; never PDF-extracted."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    claim_id: str | None = None
    decay_type: Literal["trpl", "tpv"]
    sample_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_document: str = Field(min_length=1)
    source: str = Field(default="documents/claims.jsonl", min_length=1)
    location: str = Field(min_length=1)
    source_hash: str | None = None
    reported_average: float | None = None
    reported_unit: str | None = None
    declared_formula: str | None = None
    components: list[DecayComponent] = Field(default_factory=list)
    human_confirmed: bool

    @model_validator(mode="before")
    @classmethod
    def normalize_compatible_keys(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        normalized = dict(data)
        if "record_id" not in normalized and normalized.get("claim_id"):
            normalized["record_id"] = normalized["claim_id"]
        if "decay_type" not in normalized and normalized.get("claim_type"):
            normalized["decay_type"] = normalized["claim_type"]
        if normalized.get("decay_type") == "trpl_fit":
            normalized["decay_type"] = "trpl"
        elif normalized.get("decay_type") == "tpv_fit":
            normalized["decay_type"] = "tpv"
        if "reported_average" not in normalized:
            for key in ("average_lifetime", "reported_value", "value"):
                if key in normalized:
                    normalized["reported_average"] = normalized.pop(key)
                    break
        if "reported_unit" not in normalized and "unit" in normalized:
            normalized["reported_unit"] = normalized.pop("unit")
        if "declared_formula" not in normalized:
            for key in ("average_formula", "formula"):
                if key in normalized:
                    normalized["declared_formula"] = normalized.pop(key)
                    break
        if "components" not in normalized:
            for key in ("fit_components", "parameters"):
                if key in normalized:
                    normalized["components"] = normalized.pop(key)
                    break
        if "source" not in normalized and "source_file" in normalized:
            normalized["source"] = normalized.pop("source_file")
        return normalized

    @field_validator(
        "record_id",
        "sample_id",
        "source_version",
        "source_document",
    )
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("declared_formula")
    @classmethod
    def normalize_formula_label(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        resolved = resolve_average_formula(value)
        return resolved.value if resolved is not None else " ".join(value.split())

    @model_validator(mode="after")
    def validate_record_contract(self) -> DecayFitRecord:
        if self.claim_id is None:
            self.claim_id = self.record_id
        if self.reported_average is None and not self.components:
            raise ValueError("record must include a reported average or fit components")
        if self.reported_average is not None:
            if self.reported_unit is None:
                raise ValueError("reported_unit is required with reported_average")
            normalize_decay_time(self.reported_average, self.reported_unit)
        issues = find_runtime_safety_issues(self.model_dump(mode="json"))
        if issues:
            raise ValueError("unsafe decay-fit record: " + "; ".join(issues))
        return self

    @property
    def formula(self) -> AverageLifetimeFormula | None:
        return resolve_average_formula(self.declared_formula)

    @property
    def context_key(self) -> tuple[str, str, str]:
        return (self.decay_type, self.sample_id, self.source_version)


def _coerce_components(
    components: Iterable[DecayComponent | Mapping[str, Any]],
) -> list[DecayComponent]:
    return [
        component
        if isinstance(component, DecayComponent)
        else DecayComponent.model_validate(dict(component))
        for component in components
    ]


def compute_average_lifetime(
    components: Iterable[DecayComponent | Mapping[str, Any]],
    formula: AverageLifetimeFormula | str,
    *,
    output_unit: str = "ns",
) -> float:
    """Recompute a declared biexponential average-lifetime convention."""
    normalized_components = _coerce_components(components)
    if len(normalized_components) < 2:
        raise ValueError("at least two decay components are required")
    resolved_formula = resolve_average_formula(formula)
    if resolved_formula is None:
        raise ValueError(f"unsupported average-lifetime formula: {formula!r}")

    amplitudes = [Decimal(str(component.amplitude)) for component in normalized_components]
    lifetimes_ns = [
        Decimal(str(normalize_decay_time(component.lifetime, component.unit)))
        for component in normalized_components
    ]
    if resolved_formula is AverageLifetimeFormula.AMPLITUDE_WEIGHTED:
        numerator = sum(
            (amplitude * lifetime for amplitude, lifetime in zip(amplitudes, lifetimes_ns)),
            Decimal("0"),
        )
        denominator = sum(amplitudes, Decimal("0"))
    else:
        numerator = sum(
            (
                amplitude * lifetime * lifetime
                for amplitude, lifetime in zip(amplitudes, lifetimes_ns)
            ),
            Decimal("0"),
        )
        denominator = sum(
            (amplitude * lifetime for amplitude, lifetime in zip(amplitudes, lifetimes_ns)),
            Decimal("0"),
        )
    if denominator <= 0:
        raise ValueError("average-lifetime denominator must be positive")
    average_ns = numerator / denominator
    return normalize_decay_time(float(average_ns), "ns", target_unit=output_unit)


compute_biexponential_average_lifetime = compute_average_lifetime


def _coerce_records(
    records: Iterable[DecayFitRecord | Mapping[str, Any]],
) -> list[DecayFitRecord]:
    return [
        record
        if isinstance(record, DecayFitRecord)
        else DecayFitRecord.model_validate(dict(record))
        for record in records
    ]


def _parameter_priority(record: DecayFitRecord) -> tuple[int, str]:
    priorities = {
        "source_parameters": 0,
        "source_data": 1,
        "fit_table": 2,
        "table": 2,
        "si": 3,
        "figure_annotation": 4,
        "figure": 4,
    }
    return priorities.get(record.source_document.lower(), 5), record.record_id


def _evidence_item(record: DecayFitRecord, *, role: str) -> EvidenceItem:
    return EvidenceItem(
        source=record.source,
        location=record.location,
        metadata={
            "role": role,
            "record_id": record.record_id,
            "claim_id": record.claim_id,
            "decay_type": record.decay_type,
            "sample_id": record.sample_id,
            "source_version": record.source_version,
            "source_document": record.source_document,
            "source_hash": record.source_hash,
        },
    )


def _finding_id(kind: str, reported: DecayFitRecord, parameters: DecayFitRecord | None) -> str:
    raw = ":".join(
        [kind, *reported.context_key, reported.record_id, parameters.record_id if parameters else "none"]
    )
    return "PV-DECAY-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _related_claim_ids(
    reported: DecayFitRecord,
    parameters: DecayFitRecord | None,
) -> list[str]:
    values = [reported.claim_id]
    if parameters is not None:
        values.append(parameters.claim_id)
    return [value for index, value in enumerate(values) if value and value not in values[:index]]


def _base_provenance(
    reported: DecayFitRecord,
    parameters: DecayFitRecord | None,
) -> dict[str, Any]:
    return {
        "rule_id": RULE_ID,
        "detector_id": "pv_decay_fit_consistency_v1",
        "decay_type": reported.decay_type,
        "sample_id": reported.sample_id,
        "source_version": reported.source_version,
        "source_versions": [reported.source_version],
        "related_claim_ids": _related_claim_ids(reported, parameters),
        "reported_record_id": reported.record_id,
        "parameter_record_id": parameters.record_id if parameters else None,
        "declared_formula": reported.formula.value if reported.formula else None,
        "resolution_status": "open",
        "method_family": "decay_fit_reconciliation",
    }


def _low_context_finding(
    reported: DecayFitRecord,
    parameters: DecayFitRecord | None,
    *,
    missing_formula: bool,
) -> Finding:
    provenance = _base_provenance(reported, parameters)
    provenance.update(
        {
            "open_for_scoring": False,
            "mrpi_eligible": False,
            "candidate_average_lifetimes_ns": (
                {
                    formula.value: compute_average_lifetime(
                        parameters.components if parameters else reported.components,
                        formula,
                    )
                    for formula in AverageLifetimeFormula
                }
                if len((parameters.components if parameters else reported.components)) >= 2
                else {}
            ),
        }
    )
    finding_type = (
        "decay_fit_formula_ambiguity" if missing_formula else "decay_fit_parameters_missing"
    )
    title = (
        "Average-lifetime formula needs clarification"
        if missing_formula
        else "Decay-fit parameters need verification"
    )
    safe_language = (
        "The reported decay average does not declare a supported averaging formula; "
        "verify the formula before comparing values."
        if missing_formula
        else "The declared decay average cannot be recomputed from same-sample, "
        "same-version parameters and needs source-parameter verification."
    )
    evidence = [_evidence_item(reported, role="reported_average")]
    if parameters is not None and parameters.record_id != reported.record_id:
        evidence.append(_evidence_item(parameters, role="fit_parameters"))
    return Finding(
        finding_id=_finding_id(finding_type, reported, parameters),
        type=finding_type,
        title=title,
        risk=RiskLevel.LOW,
        summary=safe_language,
        safe_report_language=safe_language,
        evidence=evidence,
        manual_verification=ManualVerification(
            needed=True,
            requests=[
                "Confirm the declared average-lifetime formula and component definitions.",
                "Provide the same-sample, same-version fit parameters and units.",
            ],
        ),
        finding_category="pv_decay_fit_consistency",
        false_positive_risks=[
            "The formula may be defined elsewhere in the methods or caption.",
            "The parameters may belong to another fit range or source version.",
        ],
        alternative_explanations=[
            "Amplitude-weighted and intensity-weighted averages are both valid when declared.",
            "Unit conversion, rounding, or a different fitted component set may explain the value.",
        ],
        limitations=[
            "No mismatch is asserted without a declared formula and matching fit parameters.",
            "Only supplied structured records are evaluated; no PDF extraction is performed.",
        ],
        provenance=provenance,
    )


def _mismatch_finding(
    reported: DecayFitRecord,
    parameters: DecayFitRecord,
    *,
    reported_ns: float,
    recomputed_ns: float,
    relative_tolerance: float,
    absolute_tolerance_ns: float,
) -> Finding:
    provenance = _base_provenance(reported, parameters)
    provenance.update(
        {
            "reported_average_ns": reported_ns,
            "recomputed_average_ns": recomputed_ns,
            "absolute_difference_ns": abs(reported_ns - recomputed_ns),
            "relative_difference": abs(reported_ns - recomputed_ns) / recomputed_ns,
            "relative_tolerance": relative_tolerance,
            "absolute_tolerance_ns": absolute_tolerance_ns,
            "open_for_scoring": True,
            "mrpi_eligible": True,
        }
    )
    safe_language = (
        "Candidate decay-fit consistency issue: the reported average differs from "
        "the declared-formula recomputation for the same sample and source version."
    )
    evidence = [_evidence_item(reported, role="reported_average")]
    if parameters.record_id != reported.record_id:
        evidence.append(_evidence_item(parameters, role="fit_parameters"))
    return Finding(
        finding_id=_finding_id("mismatch", reported, parameters),
        type="decay_fit_value_mismatch",
        title="Declared decay average differs from fit-parameter recomputation",
        risk=RiskLevel.MEDIUM,
        summary=safe_language,
        safe_report_language=safe_language,
        evidence=evidence,
        manual_verification=ManualVerification(
            needed=True,
            requests=[
                "Verify the figure annotation, fit table, and source-fit parameters for this sample/version.",
                "Confirm the averaging formula, lifetime units, fit range, and component amplitudes.",
            ],
        ),
        finding_category="pv_decay_fit_consistency",
        false_positive_risks=[
            "The annotation and parameters may use different fit ranges or preprocessing.",
            "A unit label, rounding policy, or source-version mismatch may explain the difference.",
        ],
        alternative_explanations=[
            "Amplitude-weighted and intensity-weighted averages are different valid conventions.",
            "The table may contain normalized amplitudes, rounded lifetimes, or another sample variant.",
            "A revised supplementary version may contain corrected parameters or annotations.",
        ],
        limitations=[
            "This deterministic check evaluates supplied structured values only.",
            "The candidate does not establish the cause of the visible difference.",
        ],
        provenance=provenance,
    )


def run_decay_fit_consistency_check(
    records: Iterable[DecayFitRecord | Mapping[str, Any]],
    *,
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance_ns: float = DEFAULT_ABSOLUTE_TOLERANCE_NS,
) -> list[Finding]:
    """Reconcile structured TRPL/TPV averages within sample/version groups."""
    normalized_records = [record for record in _coerce_records(records) if record.human_confirmed]
    groups: dict[tuple[str, str, str], list[DecayFitRecord]] = defaultdict(list)
    for record in normalized_records:
        groups[record.context_key].append(record)

    findings: list[Finding] = []
    for group_records in groups.values():
        parameter_records = sorted(
            [record for record in group_records if len(record.components) >= 2],
            key=_parameter_priority,
        )
        for reported in group_records:
            if reported.reported_average is None:
                continue
            parameters = reported if len(reported.components) >= 2 else (
                parameter_records[0] if parameter_records else None
            )
            if reported.formula is None:
                findings.append(
                    _low_context_finding(
                        reported,
                        parameters,
                        missing_formula=True,
                    )
                )
                continue
            if parameters is None:
                findings.append(
                    _low_context_finding(
                        reported,
                        None,
                        missing_formula=False,
                    )
                )
                continue
            try:
                reported_ns = normalize_decay_time(
                    reported.reported_average,
                    reported.reported_unit or "",
                )
                recomputed_ns = compute_average_lifetime(
                    parameters.components,
                    reported.formula,
                    output_unit="ns",
                )
            except ValueError:
                findings.append(
                    _low_context_finding(
                        reported,
                        parameters,
                        missing_formula=False,
                    )
                )
                continue
            absolute_difference = abs(reported_ns - recomputed_ns)
            relative_difference = absolute_difference / recomputed_ns
            if (
                absolute_difference <= absolute_tolerance_ns
                or relative_difference <= relative_tolerance
            ):
                continue
            findings.append(
                _mismatch_finding(
                    reported,
                    parameters,
                    reported_ns=reported_ns,
                    recomputed_ns=recomputed_ns,
                    relative_tolerance=relative_tolerance,
                    absolute_tolerance_ns=absolute_tolerance_ns,
                )
            )
    return findings


check_decay_fit_consistency = run_decay_fit_consistency_check


def _risk_not_above_ceiling(risk: str, ceiling: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    ceiling = ceiling if ceiling in order else "medium"
    return risk if order.get(risk, 0) <= order[ceiling] else ceiling


def detect_pv_decay_fit_consistency(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    """Active rule adapter; consumes only explicitly supplied structured records."""
    del package_dir
    options = options or {}
    records = options.get("records") or options.get("observations") or options.get("claims")
    if not records:
        return []
    findings = run_decay_fit_consistency_check(
        records,
        relative_tolerance=float(
            options.get("relative_tolerance", DEFAULT_RELATIVE_TOLERANCE)
        ),
        absolute_tolerance_ns=float(
            options.get("absolute_tolerance_ns", DEFAULT_ABSOLUTE_TOLERANCE_NS)
        ),
    )
    results: list[RuleExecutionResult] = []
    for finding in findings:
        record = finding.to_ledger_record()
        metadata = dict(record["provenance"])
        metadata.update(
            {
                "finding_category": record["finding_category"],
                "finding_type": record["type"],
                "runtime_status": "active",
                "execution_mode": "offline",
                "risk_ceiling": rule.risk_ceiling,
                "requires_network": False,
                "requires_private_data": False,
            }
        )
        results.append(
            RuleExecutionResult(
                finding_id=record["finding_id"],
                rule_id=rule.rule_id,
                risk_level=_risk_not_above_ceiling(
                    record["risk_level"], rule.risk_ceiling
                ),
                evidence_items=list(record["evidence"]),
                manual_verification=dict(record["manual_verification"]),
                false_positive_risks=list(record["false_positive_risks"]),
                safe_report_language=str(record["safe_report_language"]),
                alternative_explanations=list(record["alternative_explanations"]),
                missing_verification_materials=list(
                    record["manual_verification"]["requests"]
                ),
                suggested_verification_questions=list(
                    record["manual_verification"]["requests"]
                ),
                limitations=list(record["limitations"]),
                metadata=metadata,
            )
        )
    return results


__all__ = [
    "AverageLifetimeFormula",
    "DecayComponent",
    "DecayFitRecord",
    "check_decay_fit_consistency",
    "compute_average_lifetime",
    "compute_biexponential_average_lifetime",
    "detect_pv_decay_fit_consistency",
    "normalize_decay_time",
    "normalize_lifetime_to_ns",
    "resolve_average_formula",
    "run_decay_fit_consistency_check",
]
