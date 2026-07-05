from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)

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

    if not normalized.get("source_url"):
        warnings.append("case yaml missing source_url")

    public_status = normalized.get("public_status")
    if public_status not in PUBLIC_STATUS_ENUM:
        allowed = ", ".join(sorted(PUBLIC_STATUS_ENUM))
        errors.append(f"public_status {public_status!r} not in enum: {allowed}")

    if public_status == "confirmed_misconduct" and not normalized.get(
        "official_or_institutional_source"
    ):
        errors.append(
            "confirmed_misconduct requires official_or_institutional_source"
        )

    limitations = list(normalized.get("limitations") or [])
    if public_status == "allegation" and AUTO_ALLEGATION_LIMITATION not in limitations:
        limitations.append(AUTO_ALLEGATION_LIMITATION)
        normalized["limitations"] = limitations

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

    finding = Finding(
        finding_id=str(normalized.get("case_id") or path.stem),
        type="case_card_validation",
        title=title,
        risk=RiskLevel.LOW,
        summary=summary,
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
        provenance={
            "workflow": "case_distill",
            "input_kind": "case_yaml",
            "case_id": normalized.get("case_id"),
            "public_status": normalized.get("public_status"),
        },
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
