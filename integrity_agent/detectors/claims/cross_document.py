from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import ValidationError

from integrity_agent.core.claims import AtomicClaim, normalize_claim_value_and_unit
from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)
from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.core.safety import find_runtime_safety_issues
from integrity_agent.detectors.base import BaseDetector


RULE_ID = "cross_document_claim_consistency"
NUMERIC_CLAIM_TYPES = {
    "anneal_temperature",
    "concentration",
    "trpl_fit",
    "tpv_fit",
    "pce",
}
CLAIM_TYPES = {
    *NUMERIC_CLAIM_TYPES,
    "layer_order",
    "composition",
    "other",
}
SOURCE_DOCUMENTS = {
    "main",
    "si",
    "figure",
    "table",
    "source_data",
    "response",
    "correction",
}

MEDIUM_SAFE_LANGUAGE = (
    "A human-confirmed visible consistency issue is present across two source "
    "locations in the same publication version and comparison context; verify "
    "the source files, units, and version history before interpretation."
)
LOW_SAFE_LANGUAGE = (
    "A cross-document comparison question needs manual context or unit "
    "clarification; it is not an open consistency score."
)
DO_NOT_OVERCLAIM = (
    "This deterministic comparison surfaces a candidate consistency question "
    "only and does not determine intent or research misconduct."
)
ALTERNATIVE_EXPLANATIONS = [
    "The records may refer to a device or sample variant that was not distinguished in the claim context.",
    "A typographical error may explain the visible value difference.",
    "A stale supplementary information version may remain in circulation.",
    "A disclosed unit conversion, rounding step, or derived-value convention may explain the difference.",
]
DEFAULT_MANUAL_REQUESTS = [
    "Verify both cited source locations and source hashes against the supplied documents.",
    "Confirm that device variant, sample identity, measurement context, and source version match.",
    "Check units, conversions, rounding, and any disclosed derivation before scoring the issue.",
    "Check the publisher-hosted version history before treating an older mismatch as open.",
]
LIMITATIONS = [
    "Only structured, reviewer-confirmed atomic claims are compared.",
    "No claim is extracted automatically from PDF text, figures, or model output.",
    "Version authority and resolution are handled by the separate version-reconciliation workflow.",
]


@dataclass(frozen=True)
class _ClaimView:
    claim_id: str
    claim_type: str
    value: str | int | float
    unit: str
    device_variant: str
    sample_id: str | None
    measurement_context: str | None
    source_document: str
    source_version: str
    location: str
    source_hash: str
    human_confirmed: bool
    normalized_value: str | int | float | None
    normalized_unit: str | None
    normalization_error: str | None = None

    @property
    def comparison_key(self) -> tuple[str, str, str | None, str | None, str]:
        return (
            self.claim_type,
            self.device_variant,
            self.sample_id,
            self.measurement_context,
            self.source_version,
        )

    def comparison_key_dict(self) -> dict[str, str | None]:
        return {
            "claim_type": self.claim_type,
            "device_variant": self.device_variant,
            "sample_id": self.sample_id,
            "measurement_context": self.measurement_context,
            "source_version": self.source_version,
        }

    def logical_context_key_dict(self) -> dict[str, str | None]:
        return {
            "claim_type": self.claim_type,
            "device_variant": self.device_variant,
            "sample_id": self.sample_id,
            "measurement_context": self.measurement_context,
        }

    @property
    def complete_context(self) -> bool:
        return bool(self.device_variant and self.sample_id and self.measurement_context)


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _view_from_atomic(claim: AtomicClaim) -> _ClaimView:
    return _ClaimView(
        claim_id=claim.claim_id,
        claim_type=claim.claim_type,
        value=claim.value,
        unit=claim.unit,
        device_variant=claim.device_variant,
        sample_id=claim.sample_id,
        measurement_context=claim.measurement_context,
        source_document=claim.source_document,
        source_version=claim.source_version,
        location=claim.location,
        source_hash=claim.source_hash,
        human_confirmed=claim.human_confirmed,
        normalized_value=claim.normalized_value,
        normalized_unit=claim.normalized_unit,
    )


def _is_unit_only_validation_error(exc: ValidationError) -> bool:
    errors = exc.errors()
    return bool(errors) and all("unit" in str(error.get("msg", "")).lower() for error in errors)


def _view_from_unknown_unit_record(record: Mapping[str, Any]) -> _ClaimView:
    required = {
        "claim_id",
        "claim_type",
        "value",
        "unit",
        "device_variant",
        "sample_id",
        "measurement_context",
        "source_document",
        "source_version",
        "location",
        "source_hash",
        "human_confirmed",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"claim record is missing required fields: {', '.join(missing)}")
    if record["human_confirmed"] is not True:
        raise ValueError("unknown-unit review questions require human_confirmed=true")
    claim_type = str(record["claim_type"])
    source_document = str(record["source_document"])
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"unsupported claim_type: {claim_type}")
    if source_document not in SOURCE_DOCUMENTS:
        raise ValueError(f"unsupported source_document: {source_document}")

    normalized_fields = {
        "claim_id": _normalize_optional_text(record["claim_id"]),
        "device_variant": _normalize_optional_text(record["device_variant"]),
        "source_version": _normalize_optional_text(record["source_version"]),
    }
    if any(value is None for value in normalized_fields.values()):
        raise ValueError("claim identity fields must not be blank")
    location = str(record["location"])
    source_hash = str(record["source_hash"])
    if not location.strip() or not source_hash.strip():
        raise ValueError("claim evidence location and source hash must not be blank")

    unit = str(record["unit"])
    try:
        normalized_value, normalized_unit = normalize_claim_value_and_unit(
            claim_type,  # type: ignore[arg-type]
            record["value"],
            unit,
        )
    except ValueError as exc:
        normalized_value = None
        normalized_unit = None
        normalization_error = str(exc)
    else:  # Defensive: this path normally validates as AtomicClaim first.
        normalization_error = None

    return _ClaimView(
        claim_id=str(normalized_fields["claim_id"]),
        claim_type=claim_type,
        value=record["value"],
        unit=unit,
        device_variant=str(normalized_fields["device_variant"]),
        sample_id=_normalize_optional_text(record["sample_id"]),
        measurement_context=_normalize_optional_text(record["measurement_context"]),
        source_document=source_document,
        source_version=str(normalized_fields["source_version"]),
        location=location,
        source_hash=source_hash,
        human_confirmed=True,
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        normalization_error=normalization_error,
    )


def _coerce_claim(claim: AtomicClaim | Mapping[str, Any]) -> _ClaimView | None:
    if isinstance(claim, AtomicClaim):
        if not claim.eligible_for_finding:
            return None
        return _view_from_atomic(claim)
    if not isinstance(claim, Mapping):
        raise TypeError("claims must be AtomicClaim objects or mappings")

    raw = dict(claim)
    if raw.get("human_confirmed") is not True or raw.get("eligible_for_finding") is False:
        return None
    safety_issues = find_runtime_safety_issues(raw)
    if safety_issues:
        raise ValueError("unsafe claim record: " + "; ".join(sorted(set(safety_issues))))

    atomic_fields = {name: raw[name] for name in AtomicClaim.model_fields if name in raw}
    try:
        normalized = AtomicClaim.model_validate(atomic_fields)
    except ValidationError as exc:
        if not _is_unit_only_validation_error(exc):
            raise ValueError(f"invalid human-confirmed claim {raw.get('claim_id')!r}: {exc}") from exc
        return _view_from_unknown_unit_record(raw)
    if not normalized.eligible_for_finding:
        return None
    return _view_from_atomic(normalized)


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


_LAYER_SEPARATOR = re.compile(r"\s*(?:/|>|→|\||,|;)\s*")


def _layer_tokens(value: Any) -> tuple[str, ...]:
    return tuple(
        token.casefold()
        for token in _LAYER_SEPARATOR.split(str(value).strip())
        if token.strip()
    )


_IBR_RATIO = re.compile(
    r"\bI\s*:\s*Br\s*(?:=)?\s*([0-9]+(?:\.[0-9]+)?)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
    flags=re.IGNORECASE,
)


def _iodide_bromide_ratio(value: Any) -> Decimal | None:
    match = _IBR_RATIO.search(str(value))
    if not match:
        return None
    numerator = _as_decimal(match.group(1))
    denominator = _as_decimal(match.group(2))
    if numerator is None or denominator in {None, Decimal("0")}:
        return None
    return numerator / denominator


def _compare_values(first: _ClaimView, second: _ClaimView) -> tuple[str, str]:
    """Return (state, comparison_kind), where state is equal/different/question."""
    if first.normalization_error or second.normalization_error:
        return "question", "unit_review_question"

    if first.claim_type in NUMERIC_CLAIM_TYPES:
        if first.normalized_unit != second.normalized_unit:
            return "question", "unit_review_question"
        first_value = _as_decimal(first.normalized_value)
        second_value = _as_decimal(second.normalized_value)
        if first_value is None or second_value is None:
            return "question", "unit_review_question"
        return (
            ("equal", "unit_normalized_equal")
            if first_value == second_value
            else ("different", "numeric_value_change")
        )

    if first.claim_type == "layer_order":
        first_layers = _layer_tokens(first.normalized_value)
        second_layers = _layer_tokens(second.normalized_value)
        if first_layers == second_layers:
            return "equal", "layer_order_equal"
        if first_layers and Counter(first_layers) == Counter(second_layers):
            return "different", "layer_order_change"
        return "different", "layer_inventory_change"

    if first.claim_type == "composition":
        first_ratio = _iodide_bromide_ratio(first.normalized_value)
        second_ratio = _iodide_bromide_ratio(second.normalized_value)
        if first_ratio is not None and second_ratio is not None:
            if first_ratio == second_ratio:
                return "equal", "composition_ratio_equal"
            return "different", "composition_ratio_change"

    if _normalized_text(first.normalized_value) == _normalized_text(second.normalized_value):
        return "equal", "text_equal"
    return "different", "text_value_change"


def _pair_has_compatible_partial_context(first: _ClaimView, second: _ClaimView) -> bool:
    if first.claim_type != second.claim_type:
        return False
    if first.device_variant != second.device_variant:
        return False
    if first.source_version != second.source_version:
        return False
    if first.source_document == second.source_document:
        return False
    if first.sample_id and second.sample_id and first.sample_id != second.sample_id:
        return False
    if (
        first.measurement_context
        and second.measurement_context
        and first.measurement_context != second.measurement_context
    ):
        return False
    return not (first.complete_context and second.complete_context)


def _evidence_item(claim: _ClaimView) -> EvidenceItem:
    return EvidenceItem(
        source=claim.source_document,
        location=claim.location,
        metadata={
            "claim_id": claim.claim_id,
            "source_document": claim.source_document,
            "source_version": claim.source_version,
            "source_hash": claim.source_hash,
            "reported_value": claim.value,
            "reported_unit": claim.unit,
            "normalized_value": claim.normalized_value,
            "normalized_unit": claim.normalized_unit,
        },
    )


def _finding_id(first: _ClaimView, second: _ClaimView, comparison_kind: str) -> str:
    digest_input = "|".join(
        [
            RULE_ID,
            *sorted([first.claim_id, second.claim_id]),
            first.source_version,
            comparison_kind,
        ]
    )
    return "CD-" + hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:12].upper()


def _build_finding(
    first: _ClaimView,
    second: _ClaimView,
    *,
    risk: RiskLevel,
    comparison_kind: str,
    rule: DetectorRule | None,
) -> Finding:
    is_open = risk is RiskLevel.MEDIUM
    safe_language = (
        rule.safe_report_language
        if is_open and rule is not None
        else MEDIUM_SAFE_LANGUAGE if is_open else LOW_SAFE_LANGUAGE
    )
    manual_requests = list(rule.manual_verification) if rule is not None else list(DEFAULT_MANUAL_REQUESTS)
    false_positive_risks = (
        list(rule.false_positive_risks)
        if rule is not None
        else list(ALTERNATIVE_EXPLANATIONS)
    )
    comparison_key = first.comparison_key_dict()
    logical_context_key = first.logical_context_key_dict()
    return Finding(
        finding_id=_finding_id(first, second, comparison_kind),
        type=(
            "visible_consistency_issue"
            if is_open
            else "cross_document_verification_question"
        ),
        title=(
            "Human-confirmed cross-document visible consistency issue"
            if is_open
            else "Cross-document context or unit verification question"
        ),
        risk=risk,
        summary=(
            "Two human-confirmed source locations in the same version and context show different normalized claim values."
            if is_open
            else "The supplied human-confirmed claims cannot be compared as an open issue until missing context or units are clarified."
        ),
        evidence=[_evidence_item(first), _evidence_item(second)],
        manual_verification=ManualVerification(needed=True, requests=manual_requests),
        safe_report_language=safe_language,
        finding_category=RULE_ID,
        false_positive_risks=false_positive_risks,
        alternative_explanations=list(ALTERNATIVE_EXPLANATIONS),
        limitations=list(LIMITATIONS),
        provenance={
            "rule_id": RULE_ID,
            "comparison_key": comparison_key,
            "logical_context_key": logical_context_key,
            "comparison_kind": comparison_kind,
            "related_claim_ids": [first.claim_id, second.claim_id],
            "source_version": first.source_version,
            "source_versions": [first.source_version],
            "human_confirmed": True,
            "open_for_scoring": is_open,
            "mrpi_eligible": is_open,
            "resolution_status": "open" if is_open else "needs_context",
            "do_not_overclaim": DO_NOT_OVERCLAIM,
        },
    )


def compare_cross_document_claims(
    claims: Iterable[AtomicClaim | Mapping[str, Any]],
    *,
    rule: DetectorRule | None = None,
) -> list[Finding]:
    """Compare only reviewer-confirmed claims in the same exact source context.

    The source version is part of the comparison key. The parallel
    ``logical_context_key`` deliberately omits it so a separate reconciliation
    workflow can later relate stale and revised publisher versions without this
    detector deciding which version is authoritative.
    """
    normalized = [view for claim in claims if (view := _coerce_claim(claim)) is not None]
    findings: list[Finding] = []

    for index, first in enumerate(normalized):
        for second in normalized[index + 1 :]:
            if first.source_document == second.source_document:
                continue

            if first.complete_context and second.complete_context:
                if first.comparison_key != second.comparison_key:
                    continue
                state, comparison_kind = _compare_values(first, second)
                if state == "equal":
                    continue
                risk = RiskLevel.LOW if state == "question" else RiskLevel.MEDIUM
                findings.append(
                    _build_finding(
                        first,
                        second,
                        risk=risk,
                        comparison_kind=comparison_kind,
                        rule=rule,
                    )
                )
                continue

            if not _pair_has_compatible_partial_context(first, second):
                continue
            state, comparison_kind = _compare_values(first, second)
            if state == "equal":
                continue
            findings.append(
                _build_finding(
                    first,
                    second,
                    risk=RiskLevel.LOW,
                    comparison_kind=(
                        comparison_kind
                        if comparison_kind == "unit_review_question"
                        else "missing_comparison_context"
                    ),
                    rule=rule,
                )
            )

    return findings


detect_cross_document_claim_consistency = compare_cross_document_claims


def _load_claim_records(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} line {line_number}: invalid JSON ({exc.msg})") from exc
            if not isinstance(record, Mapping):
                raise ValueError(f"{path.name} line {line_number}: claim must be an object")
            records.append(record)
    return records


class CrossDocumentClaimConsistencyDetector(BaseDetector):
    runtime_status = "active"
    execution_mode = "offline"
    risk_ceiling = "medium"
    requires_network = False
    requires_private_data = False

    def detect(
        self,
        package_dir: Path,
        rule: DetectorRule,
        options: dict[str, Any] | None = None,
    ) -> list[RuleExecutionResult]:
        options = options or {}
        supplied_claims = options.get("claims")
        if supplied_claims is None:
            claims_path = options.get("claims_path")
            if claims_path is None:
                claims_path = Path(package_dir) / "documents" / "claims.jsonl"
            else:
                claims_path = Path(claims_path)
                if not claims_path.is_absolute():
                    claims_path = Path(package_dir) / claims_path
            if not claims_path.is_file():
                return []
            supplied_claims = _load_claim_records(claims_path)

        findings = compare_cross_document_claims(supplied_claims, rule=rule)
        results: list[RuleExecutionResult] = []
        for finding in findings:
            ledger = finding.to_ledger_record()
            manual = ledger["manual_verification"]
            results.append(
                RuleExecutionResult(
                    finding_id=finding.finding_id,
                    rule_id=rule.rule_id,
                    risk_level=finding.risk.value,
                    evidence_items=list(ledger["evidence"]),
                    manual_verification=dict(manual),
                    false_positive_risks=[str(item) for item in finding.false_positive_risks],
                    safe_report_language=str(finding.safe_report_language),
                    alternative_explanations=[str(item) for item in finding.alternative_explanations],
                    missing_verification_materials=list(manual["requests"]),
                    suggested_verification_questions=list(manual["requests"]),
                    limitations=[str(item) for item in finding.limitations],
                    metadata=dict(finding.provenance),
                )
            )
        return results


def run_cross_document_claim_consistency(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return CrossDocumentClaimConsistencyDetector().detect(package_dir, rule, options)


__all__ = [
    "CrossDocumentClaimConsistencyDetector",
    "compare_cross_document_claims",
    "detect_cross_document_claim_consistency",
    "run_cross_document_claim_consistency",
]
