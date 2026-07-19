from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.claims.cross_document import compare_cross_document_claims
from integrity_agent.workflows.validate_ledger import validate_ledger_file


DEFAULT_OUTPUT_DIR = Path("outputs") / "cross_document_review"
FINDINGS_NAME = "cross_document_findings.jsonl"
SUMMARY_NAME = "cross_document_review_summary.md"


class CrossDocumentReviewError(ValueError):
    """Raised when structured claim input or ledger output is invalid."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_claims_path(input_path: Path | str) -> Path:
    path = Path(input_path)
    if path.is_dir():
        package_claims = path / "documents" / "claims.jsonl"
        direct_claims = path / "claims.jsonl"
        path = package_claims if package_claims.is_file() else direct_claims
    if not path.is_file():
        raise CrossDocumentReviewError(f"structured claims JSONL not found: {path.name}")
    if path.suffix.lower() != ".jsonl":
        raise CrossDocumentReviewError("cross-document review accepts structured JSONL claims only")
    return path


def _load_claim_records(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise CrossDocumentReviewError(
                    f"{path.name} line {line_number}: invalid JSON ({exc.msg})"
                ) from exc
            if not isinstance(record, Mapping):
                raise CrossDocumentReviewError(
                    f"{path.name} line {line_number}: claim record must be an object"
                )
            claim_id = record.get("claim_id")
            if not isinstance(claim_id, str) or not claim_id.strip():
                raise CrossDocumentReviewError(
                    f"{path.name} line {line_number}: claim_id must be a non-empty string"
                )
            if claim_id in seen_ids:
                raise CrossDocumentReviewError(
                    f"{path.name} line {line_number}: duplicate claim_id {claim_id!r}"
                )
            seen_ids.add(claim_id)
            records.append(record)
    return records


def _write_summary(path: Path, *, claim_count: int, findings: list[dict[str, Any]]) -> None:
    medium_count = sum(1 for finding in findings if finding["risk_level"] == "medium")
    low_count = sum(1 for finding in findings if finding["risk_level"] == "low")
    lines = [
        "# Cross-document Claim Review Summary",
        "",
        "## Offline structured review",
        f"- Human-supplied claim records inspected: {claim_count}",
        f"- Open medium visible-consistency issues: {medium_count}",
        f"- Low context/unit verification questions: {low_count}",
        "- Automatic PDF, image, OCR, or model extraction performed: no",
        "- Network used: no",
        "",
        "## Findings",
    ]
    if findings:
        for finding in findings:
            provenance = finding.get("provenance") or {}
            lines.extend(
                [
                    f"- `{finding['finding_id']}` ({finding['risk_level']}): {finding['safe_report_language']}",
                    f"  - Related claims: {', '.join(provenance.get('related_claim_ids', []))}",
                    f"  - Comparison kind: {provenance.get('comparison_kind', 'unspecified')}",
                ]
            )
    else:
        lines.append("- No cross-document candidate issue was produced from the eligible claims.")
    lines.extend(
        [
            "",
            "## Do-not-overclaim notice",
            "- These records are deterministic consistency questions for manual review.",
            "- They do not determine intent or research misconduct.",
            "- Publication-version authority and resolution require the separate version-reconciliation workflow.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_cross_document_review(
    input_path: Path | str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Compare structured reviewer-confirmed claims and write a valid ledger."""
    claims_path = _resolve_claims_path(input_path)
    claims = _load_claim_records(claims_path)
    rules = load_rule_registry(_project_root() / "knowledge_base" / "detector_rules")
    rule = rules["cross_document_claim_consistency"]
    findings = compare_cross_document_claims(claims, rule=rule)
    records = [finding.to_ledger_record() for finding in findings]

    resolved_output = Path(output_dir)
    resolved_output.mkdir(parents=True, exist_ok=True)
    findings_path = resolved_output / FINDINGS_NAME
    summary_path = resolved_output / SUMMARY_NAME
    findings_tmp = findings_path.with_suffix(findings_path.suffix + ".tmp")
    summary_tmp = summary_path.with_suffix(summary_path.suffix + ".tmp")

    with findings_tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    validation = validate_ledger_file(findings_tmp)
    if not validation.ok:
        findings_tmp.unlink(missing_ok=True)
        details = "; ".join(issue.format() for issue in validation.issues)
        raise CrossDocumentReviewError(f"cross-document ledger validation failed: {details}")

    _write_summary(summary_tmp, claim_count=len(claims), findings=records)
    findings_tmp.replace(findings_path)
    summary_tmp.replace(summary_path)
    return findings_path.resolve(), summary_path.resolve()


__all__ = [
    "CrossDocumentReviewError",
    "run_cross_document_review",
]
