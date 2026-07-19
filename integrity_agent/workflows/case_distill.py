from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)
from integrity_agent.core.evidence.scope import FindingScope
from integrity_agent.core.safety import find_runtime_safety_issues

PUBLIC_STATUS_ENUM = {
    "confirmed_misconduct",
    "allegation",
    "investigation_started",
    "retracted",
    "mass_retraction",
    "settlement_or_legal_resolution",
    "published_method",
    "public_method_example",
    "methodology_only",
    "policy_resource",
    "unresolved",
}

AUTO_ALLEGATION_LIMITATION = "not independently verified"

CASE_CARD_REQUIRED_FIELDS = (
    "case_id",
    "priority",
    "source_type",
    "source_url",
    "field",
    "public_status",
    "evidence_patterns",
    "detector_candidates",
    "manual_verification_needed",
    "false_positive_risks",
    "safe_report_language",
)
VALIDATION_MODES = {"production", "toy", "draft"}
RELAXED_VALIDATION_MODES = {"toy", "draft"}
EVIDENCE_TIER_ENUM = {"E0", "E1", "E2", "E3", "E4"}
COUNTER_SOURCE_TYPE_ENUM = {
    "author_response",
    "publisher_update",
    "correction",
    "raw_data_offer",
    "other",
}
RESOLUTION_STATUS_ENUM = {
    "open",
    "partially_explained",
    "resolved_by_version",
    "formally_corrected",
    "unresolved",
}
PUBLIC_METHOD_STATUS_ENUM = {"public_method_example", "unresolved"}
PUBLISHER_RESOLUTION_SOURCE_TYPES = {"publisher_update", "correction"}
CASE_PROVENANCE_FIELDS = (
    "scope",
    "target_doi",
    "source_accessed_at",
    "source_snapshot_hash",
    "evidence_tier",
    "counter_sources",
    "resolution_status",
    "version_timeline",
)
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


class CaseValidationError(ValueError):
    """Raised when a YAML case card violates the safe-review contract."""

    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class CaseValidationResult:
    card: dict[str, Any]
    warnings: list[str]


def _is_iso8601(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_counter_sources(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return ["counter_sources must be a list"]

    errors: list[str] = []
    for index, source in enumerate(value):
        prefix = f"counter_sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        url = source.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            errors.append(f"{prefix}.url must be a public HTTP(S) URL")
        source_type = source.get("source_type")
        if source_type not in COUNTER_SOURCE_TYPE_ENUM:
            allowed = ", ".join(sorted(COUNTER_SOURCE_TYPE_ENUM))
            errors.append(f"{prefix}.source_type {source_type!r} not in enum: {allowed}")
        if not _is_iso8601(source.get("observed_at")):
            errors.append(f"{prefix}.observed_at must be ISO-8601")
    return errors


def _validate_version_timeline(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return ["version_timeline must be a list"]

    errors: list[str] = []
    for index, event in enumerate(value):
        prefix = f"version_timeline[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        source_type = event.get("source_type")
        if not isinstance(source_type, str) or not source_type.strip():
            errors.append(f"{prefix}.source_type must be a non-empty string")
        if not _is_iso8601(event.get("observed_at")):
            errors.append(f"{prefix}.observed_at must be ISO-8601")
        source_url = event.get("source_url")
        if source_url is not None and (
            not isinstance(source_url, str)
            or not source_url.startswith(("https://", "http://"))
        ):
            errors.append(f"{prefix}.source_url must be a public HTTP(S) URL")
    return errors


def summarize_case_note(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    paragraphs = [line for line in lines if line and not line.startswith("#")]
    if not paragraphs:
        return "Toy case note with no narrative content."
    return " ".join(paragraphs)[:500]


def title_from_case_note(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
    return path.stem.replace("_", " ").title()


def distill_case_note(path: Path, source_label: str | None = None) -> Finding:
    text = path.read_text(encoding="utf-8")
    title = title_from_case_note(path, text)
    summary = summarize_case_note(text)

    return Finding(
        finding_id="F001",
        type="case_distillation_note",
        title=title,
        risk=RiskLevel.LOW,
        summary=summary,
        evidence=[
            EvidenceItem(
                source=source_label or str(path),
                location="case note",
                quote=summary[:240],
            )
        ],
        manual_verification=ManualVerification(
            needed=True,
            requests=[
                "Check the public source and original materials before turning this note into a detector rule.",
                "Document false-positive risks and safe reporting language.",
            ],
        ),
        false_positive_risks=[
            "Toy or incomplete notes may omit benign explanations.",
            "A visible pattern may be caused by rounding, normalization, reuse with disclosure, or metadata loss.",
        ],
        alternative_explanations=[
            "The note may describe a legitimate derived value or intentionally reused control.",
        ],
        limitations=[
            "This stub only converts a note into a traceable ledger entry; it does not validate the claim.",
        ],
        provenance={
            "workflow": "case_distill",
            "input_kind": "markdown_note",
        },
    )


def load_yaml_case(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only in minimal envs
        raise CaseValidationError(["PyYAML is required to validate YAML case cards."]) from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CaseValidationError(["case yaml must contain a mapping at the top level"])
    return data


def validate_case_card(card: dict[str, Any]) -> CaseValidationResult:
    normalized = dict(card)
    warnings: list[str] = []
    errors: list[str] = []

    validation_mode = normalized.get("validation_mode", "production")
    is_relaxed = (
        isinstance(validation_mode, str)
        and validation_mode in RELAXED_VALIDATION_MODES
    )
    if not isinstance(validation_mode, str) or validation_mode not in VALIDATION_MODES:
        allowed = ", ".join(sorted(VALIDATION_MODES))
        errors.append(f"validation_mode {validation_mode!r} not in enum: {allowed}")

    if not is_relaxed:
        missing = [
            field
            for field in CASE_CARD_REQUIRED_FIELDS
            if field not in normalized or normalized[field] in (None, "", [])
        ]
        if missing:
            errors.append(f"missing required fields: {missing}")

    if not normalized.get("source_url") and is_relaxed:
        warnings.append("case yaml missing source_url")

    public_status = normalized.get("public_status")
    if public_status is not None and public_status not in PUBLIC_STATUS_ENUM:
        allowed = ", ".join(sorted(PUBLIC_STATUS_ENUM))
        errors.append(f"public_status {public_status!r} not in enum: {allowed}")

    if public_status == "confirmed_misconduct" and not normalized.get(
        "official_or_institutional_source"
    ):
        errors.append(
            "confirmed_misconduct requires official_or_institutional_source"
        )

    source_type = normalized.get("source_type")
    is_public_method = source_type == "public_method"
    if is_public_method:
        missing_provenance = [
            field
            for field in (
                "target_doi",
                "source_accessed_at",
                "evidence_tier",
                "resolution_status",
                "scope",
            )
            if field not in normalized or normalized[field] in (None, "")
        ]
        if missing_provenance:
            errors.append(
                f"public_method missing required provenance fields: {missing_provenance}"
            )
        if public_status not in PUBLIC_METHOD_STATUS_ENUM:
            allowed = ", ".join(sorted(PUBLIC_METHOD_STATUS_ENUM))
            errors.append(
                f"public_method public_status {public_status!r} not in enum: {allowed}"
            )

    scope = normalized.get("scope")
    if scope is not None and scope not in {item.value for item in FindingScope}:
        allowed = ", ".join(item.value for item in FindingScope)
        errors.append(f"scope {scope!r} not in enum: {allowed}")
    if scope == FindingScope.UNSUPPORTED_MOTIVE.value:
        errors.append("unsupported_motive cannot be distilled into a finding")

    target_doi = normalized.get("target_doi")
    if target_doi is not None and (
        not isinstance(target_doi, str) or not DOI_RE.fullmatch(target_doi.strip())
    ):
        errors.append("target_doi must be a DOI beginning with 10.<registrant>/")

    source_accessed_at = normalized.get("source_accessed_at")
    if source_accessed_at is not None and not _is_iso8601(source_accessed_at):
        errors.append("source_accessed_at must be ISO-8601")

    source_snapshot_hash = normalized.get("source_snapshot_hash")
    if source_snapshot_hash is not None and not isinstance(source_snapshot_hash, str):
        errors.append("source_snapshot_hash must be a string or null")

    evidence_tier = normalized.get("evidence_tier")
    if evidence_tier is not None and evidence_tier not in EVIDENCE_TIER_ENUM:
        allowed = ", ".join(sorted(EVIDENCE_TIER_ENUM))
        errors.append(f"evidence_tier {evidence_tier!r} not in enum: {allowed}")

    resolution_status = normalized.get("resolution_status")
    if (
        resolution_status is not None
        and resolution_status not in RESOLUTION_STATUS_ENUM
    ):
        allowed = ", ".join(sorted(RESOLUTION_STATUS_ENUM))
        errors.append(
            f"resolution_status {resolution_status!r} not in enum: {allowed}"
        )

    counter_sources = normalized.get("counter_sources")
    errors.extend(_validate_counter_sources(counter_sources))
    errors.extend(_validate_version_timeline(normalized.get("version_timeline")))

    if resolution_status in {"resolved_by_version", "formally_corrected"}:
        if not isinstance(counter_sources, list) or not counter_sources:
            errors.append(
                f"resolution_status {resolution_status!r} requires at least one counter source"
            )
        else:
            publisher_sources = {
                source.get("source_type")
                for source in counter_sources
                if isinstance(source, dict)
            }
            if not publisher_sources.intersection(PUBLISHER_RESOLUTION_SOURCE_TYPES):
                errors.append(
                    f"resolution_status {resolution_status!r} requires a publisher "
                    "counter source (publisher_update or correction)"
                )

    limitations = list(normalized.get("limitations") or [])
    if public_status == "allegation" and AUTO_ALLEGATION_LIMITATION not in limitations:
        limitations.append(AUTO_ALLEGATION_LIMITATION)
        normalized["limitations"] = limitations

    errors.extend(find_runtime_safety_issues(normalized))

    if errors:
        raise CaseValidationError(errors=errors, warnings=warnings)

    return CaseValidationResult(card=normalized, warnings=warnings)


def summarize_yaml_case(card: dict[str, Any]) -> str:
    if card.get("summary"):
        return str(card["summary"])[:500]
    patterns = ", ".join(str(item) for item in card.get("evidence_patterns", [])[:5])
    detectors = ", ".join(str(item) for item in card.get("detector_candidates", [])[:5])
    if patterns or detectors:
        return f"Case card draft. Evidence patterns: {patterns}. Detector candidates: {detectors}."[:500]
    return "Case card draft requiring manual verification before detector implementation."


def distill_yaml_case(path: Path, source_label: str | None = None) -> tuple[Finding, list[str]]:
    card = load_yaml_case(path)
    validation = validate_case_card(card)
    normalized = validation.card

    source = normalized.get("source_url") or source_label or str(path)
    title = str(normalized.get("title") or normalized.get("case_id") or path.stem)
    summary = summarize_yaml_case(normalized)
    verification_requests = list(normalized.get("manual_verification_needed") or [])
    if not verification_requests:
        verification_requests = [
            "Check public source, original data/images/metadata, and author or institutional context before drawing conclusions."
        ]

    provenance = {
        "workflow": "case_distill",
        "input_kind": "case_yaml",
        "case_id": normalized.get("case_id"),
        "public_status": normalized.get("public_status"),
    }
    provenance.update(
        {
            field: normalized[field]
            for field in CASE_PROVENANCE_FIELDS
            if field in normalized
        }
    )

    finding = Finding(
        finding_id=str(normalized.get("case_id") or path.stem),
        type="case_card_validation",
        title=title,
        risk=RiskLevel.LOW,
        summary=summary,
        safe_report_language=normalized.get("safe_report_language"),
        evidence=[
            EvidenceItem(
                source=str(source),
                location="case yaml",
                quote=summary[:240],
                metadata={
                    "source_type": normalized.get("source_type"),
                    "public_status": normalized.get("public_status"),
                },
            )
        ],
        manual_verification=ManualVerification(
            needed=True,
            requests=[str(item) for item in verification_requests],
        ),
        false_positive_risks=[str(item) for item in normalized.get("false_positive_risks", [])],
        alternative_explanations=[
            str(item) for item in normalized.get("alternative_explanations", [])
        ],
        limitations=[str(item) for item in normalized.get("limitations", [])],
        provenance=provenance,
        scope=FindingScope(
            normalized.get("scope", FindingScope.RESEARCH_INTEGRITY.value)
        ),
    )
    return finding, validation.warnings


def run_case_distill(
    input_path: Path,
    output_path: Path,
    *,
    emit_warning: Callable[[str], None] | None = None,
) -> Path:
    source_label = input_path.as_posix()
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser()
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if input_path.suffix.lower() in {".yml", ".yaml"}:
        finding, warnings = distill_yaml_case(input_path, source_label=source_label)
        if emit_warning:
            for warning in warnings:
                emit_warning(warning)
    else:
        finding = distill_case_note(input_path, source_label=source_label)

    output_path.write_text(finding.to_json_line() + "\n", encoding="utf-8")
    return output_path.resolve()
