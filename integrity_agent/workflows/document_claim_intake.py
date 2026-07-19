from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from integrity_agent.core.claims import AtomicClaim


DEFAULT_OUTPUT_DIR = Path("outputs") / "document_claim_intake"
NORMALIZED_CLAIMS_NAME = "document_claims.jsonl"
INTAKE_MANIFEST_NAME = "document_claim_intake_manifest.json"


class DocumentClaimIntakeError(ValueError):
    def __init__(self, issues: list[str] | str):
        self.issues = [issues] if isinstance(issues, str) else list(issues)
        super().__init__("; ".join(self.issues))


def _resolve_claims_path(input_path: Path | str) -> Path:
    path = Path(input_path)
    if path.is_dir():
        path = path / "claims.jsonl"
    if path.name != "claims.jsonl" or path.suffix.lower() != ".jsonl":
        raise DocumentClaimIntakeError(
            "document claim intake accepts only a structured claims.jsonl file; PDF/OCR/LLM extraction is not performed"
        )
    if not path.is_file():
        raise DocumentClaimIntakeError(f"claims.jsonl not found: {path.name}")
    return path


def _safe_source_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def load_document_claims(input_path: Path | str) -> tuple[list[AtomicClaim], list[str], Path]:
    claims_path = _resolve_claims_path(input_path)
    claims: list[AtomicClaim] = []
    warnings: list[str] = []
    issues: list[str] = []
    seen_ids: set[str] = set()

    with claims_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                warnings.append(f"line {line_number}: blank line ignored")
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                issues.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(payload, dict):
                issues.append(f"line {line_number}: claim record must be a JSON object")
                continue
            try:
                claim = AtomicClaim.model_validate(payload)
            except ValidationError as exc:
                details = "; ".join(
                    f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                    for error in exc.errors()
                )
                issues.append(f"line {line_number}: {details}")
                continue
            if claim.claim_id in seen_ids:
                issues.append(f"line {line_number}: duplicate claim_id {claim.claim_id!r}")
                continue
            seen_ids.add(claim.claim_id)
            claims.append(claim)
            if not claim.human_confirmed:
                warnings.append(
                    f"line {line_number}: claim {claim.claim_id!r} retained as a draft candidate and excluded from findings"
                )

    if issues:
        raise DocumentClaimIntakeError(issues)
    if not claims:
        warnings.append("claims.jsonl contains no claim records")
    return claims, warnings, claims_path


def _write_outputs(
    claims: list[AtomicClaim],
    warnings: list[str],
    claims_path: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = output_dir / NORMALIZED_CLAIMS_NAME
    manifest_path = output_dir / INTAKE_MANIFEST_NAME
    normalized_tmp = normalized_path.with_suffix(normalized_path.suffix + ".tmp")
    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")

    with normalized_tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for claim in claims:
            handle.write(json.dumps(claim.to_record(), ensure_ascii=False, sort_keys=True) + "\n")

    confirmed_count = sum(1 for claim in claims if claim.human_confirmed)
    draft_count = len(claims) - confirmed_count
    status = "warning" if warnings else "success"
    source_label = _safe_source_label(claims_path)
    manifest: dict[str, Any] = {
        "schema_version": "v1",
        "module_name": "document-claim-intake",
        "status": status,
        "input_file": source_label,
        "input_record_count": len(claims),
        "confirmed_claim_count": confirmed_count,
        "draft_candidate_count": draft_count,
        "finding_count": 0,
        "risk_ceiling": "medium",
        "safe_report_language": (
            "Structured claim intake is not a finding; any later candidate signal requires manual review."
        ),
        "warnings": warnings,
        "automatic_extraction_performed": False,
        "network_used": False,
        "output_files": [NORMALIZED_CLAIMS_NAME, INTAKE_MANIFEST_NAME],
        "module_status": {
            "module_name": "document-claim-intake",
            "status": status,
            "input_path": source_label,
            "output_paths": [NORMALIZED_CLAIMS_NAME, INTAKE_MANIFEST_NAME],
            "warnings": warnings,
            "input_artifact_count": 1,
            "parsed_row_count": len(claims),
            "finding_count": 0,
        },
    }
    manifest_tmp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    normalized_tmp.replace(normalized_path)
    manifest_tmp.replace(manifest_path)
    return normalized_path.resolve(), manifest_path.resolve()


def run_document_claim_intake(
    input_path: Path | str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Validate and normalize human-located JSONL claims, entirely offline."""
    claims, warnings, claims_path = load_document_claims(input_path)
    return _write_outputs(claims, warnings, claims_path, Path(output_dir))
