from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from integrity_agent.core.tables.table_schema import TableManifestItem
from integrity_agent.domains.photovoltaics.schema import (
    PVConsistencyFinding,
    build_pv_metric_rows,
)
from integrity_agent.domains.photovoltaics.field_mapping import infer_pv_field_mapping
from integrity_agent.domains.photovoltaics.pce_consistency import run_pce_consistency_check
from integrity_agent.domains.photovoltaics.eqe_jv_consistency import run_eqe_jv_jsc_consistency_check
from integrity_agent.domains.photovoltaics.voc_loss import run_voc_loss_check
from integrity_agent.domains.photovoltaics.reporting_completeness import run_pv_reporting_completeness_check
from integrity_agent.domains.photovoltaics.stability_reporting import run_pv_stability_reporting_check
from integrity_agent.domains.photovoltaics.tandem_consistency import run_tandem_consistency_check
from integrity_agent.domains.photovoltaics.materials_characterization import run_materials_characterization_check
from integrity_agent.domains.photovoltaics.decay_fit_consistency import (
    DecayFitRecord,
    run_decay_fit_consistency_check,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file

DEFAULT_OUTPUT_DIR = Path("outputs") / "pv_domain"
DECAY_FINDINGS_NAME = "pv_decay_fit_findings.jsonl"
DECAY_SUMMARY_NAME = "pv_decay_fit_summary.md"


class PVDecayFitReviewError(ValueError):
    def __init__(self, issues: list[str] | str):
        self.issues = [issues] if isinstance(issues, str) else list(issues)
        super().__init__("; ".join(self.issues))

def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _safe_decay_input_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def _decay_output_paths(output_dir: Path) -> tuple[Path, Path]:
    return output_dir / DECAY_FINDINGS_NAME, output_dir / DECAY_SUMMARY_NAME


def _clear_decay_outputs(output_dir: Path) -> None:
    findings_path, summary_path = _decay_output_paths(output_dir)
    for path in (
        findings_path,
        summary_path,
        findings_path.with_suffix(findings_path.suffix + ".tmp"),
        summary_path.with_suffix(summary_path.suffix + ".tmp"),
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _load_decay_fit_records(
    records_path: Path,
) -> tuple[list[DecayFitRecord], list[str]]:
    records: list[DecayFitRecord] = []
    warnings: list[str] = []
    issues: list[str] = []
    seen_ids: set[str] = set()

    with records_path.open(encoding="utf-8") as handle:
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
                issues.append(f"line {line_number}: decay-fit record must be a JSON object")
                continue
            try:
                record = DecayFitRecord.model_validate(payload)
            except ValidationError as exc:
                details = "; ".join(
                    f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                    for error in exc.errors()
                )
                issues.append(f"line {line_number}: {details}")
                continue
            if record.record_id in seen_ids:
                issues.append(
                    f"line {line_number}: duplicate record_id {record.record_id!r}"
                )
                continue
            seen_ids.add(record.record_id)
            records.append(record)

    if issues:
        raise PVDecayFitReviewError(issues)
    if not records:
        warnings.append("No structured decay-fit records were supplied")
    return records, warnings


def _write_decay_summary(
    path: Path,
    *,
    input_label: str,
    records: list[DecayFitRecord],
    finding_records: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    confirmed_count = sum(1 for record in records if record.human_confirmed)
    draft_count = len(records) - confirmed_count
    status = "warning" if warnings else "success"
    risk_counts = {
        risk: sum(1 for record in finding_records if record.get("risk_level") == risk)
        for risk in ("low", "medium", "high")
    }
    lines = [
        "# PV Decay-Fit Structured Review Summary",
        "",
        f"- Status: {status}",
        f"- Input: `{input_label}`",
        f"- Input records: {len(records)}",
        f"- Human-confirmed records: {confirmed_count}",
        f"- Draft records excluded from findings: {draft_count}",
        f"- Findings: {len(finding_records)}",
        f"- Risk counts: low={risk_counts['low']}, medium={risk_counts['medium']}, high={risk_counts['high']}",
        "",
        "## Warnings",
    ]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Safety and interpretation",
            "- This wrapper reads structured JSONL records only and performs no PDF, image, OCR, or language-model extraction.",
            "- A mismatch is a candidate consistency signal requiring formula, unit, sample, source-version, and fit-parameter verification.",
            "- Missing or unsupported formula context remains low risk and is excluded from open scoring.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_pv_decay_fit_review(
    records_path: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path]:
    """Review explicit structured TRPL/TPV JSONL records, entirely offline.

    This wrapper is intentionally separate from the legacy table-derived PV
    dataclasses. It never attempts PDF/OCR extraction.
    """
    input_path = Path(records_path)
    resolved_out = (
        DEFAULT_OUTPUT_DIR / "decay_fit"
        if output_dir is None
        else Path(output_dir)
    )
    target_findings, target_summary = _decay_output_paths(resolved_out)
    input_resolved = input_path.resolve()
    if input_resolved in {
        target_findings.resolve(),
        target_summary.resolve(),
    }:
        raise PVDecayFitReviewError(
            "structured input and generated output paths must differ"
        )
    _clear_decay_outputs(resolved_out)
    if input_path.suffix.lower() != ".jsonl":
        raise PVDecayFitReviewError(
            "PV decay-fit review accepts structured JSONL only; PDF/OCR extraction is not performed"
        )
    if not input_path.is_file():
        raise PVDecayFitReviewError(f"structured JSONL file not found: {input_path.name}")

    try:
        records, warnings = _load_decay_fit_records(input_path)
    except (OSError, PVDecayFitReviewError) as exc:
        _clear_decay_outputs(resolved_out)
        if isinstance(exc, PVDecayFitReviewError):
            raise
        raise PVDecayFitReviewError(f"could not read structured JSONL: {exc}") from exc

    findings = run_decay_fit_consistency_check(records)
    finding_records = [finding.to_ledger_record() for finding in findings]

    resolved_out.mkdir(parents=True, exist_ok=True)
    findings_path, summary_path = _decay_output_paths(resolved_out)
    findings_tmp = findings_path.with_suffix(findings_path.suffix + ".tmp")
    summary_tmp = summary_path.with_suffix(summary_path.suffix + ".tmp")
    try:
        _write_jsonl(findings_tmp, finding_records)
        validation = validate_ledger_file(findings_tmp)
        if not validation.ok:
            details = "; ".join(issue.format() for issue in validation.issues)
            raise PVDecayFitReviewError(
                "generated PV decay-fit ledger failed validation: " + details
            )
        _write_decay_summary(
            summary_tmp,
            input_label=_safe_decay_input_label(input_path),
            records=records,
            finding_records=finding_records,
            warnings=warnings,
        )
        findings_tmp.replace(findings_path)
        summary_tmp.replace(summary_path)
    except Exception:
        _clear_decay_outputs(resolved_out)
        raise
    return findings_path.resolve(), summary_path.resolve()

def run_pv_domain_review(
    manifest_path: Path | str,
    column_profiles_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    table_base_dir: Path | str | None = None,
    pce_tolerance_abs: float = 0.3,
    pce_tolerance_rel: float = 0.03,
    eqe_jsc_tolerance_rel: float = 0.10,
    eqe_jsc_tolerance_abs: float = 1.0,
) -> tuple[Path, Path, Path, Path]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest path not found: {manifest_path}")

    resolved_out = DEFAULT_OUTPUT_DIR if output_dir is None else Path(output_dir)
    resolved_out.mkdir(parents=True, exist_ok=True)

    # 1. Build PV Metric Rows
    pv_rows = build_pv_metric_rows(
        manifest_path,
        column_profiles_path,
        table_base_dir=table_base_dir,
    )

    # Load manifest items for column mappings output
    items: list[TableManifestItem] = []
    with manifest_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(TableManifestItem(**json.loads(line)))

    # Extract all field mappings
    mappings_records = []
    for item in items:
        for col in item.columns:
            mapping = infer_pv_field_mapping(col)
            if mapping:
                mappings_records.append({
                    "table_id": item.table_id,
                    "source_file": item.source_file,
                    "column": col,
                    "mapping": mapping.to_dict()
                })

    # Collect row warnings
    warnings_records = []
    for r in pv_rows:
        if r.warnings:
            warnings_records.append({
                "row_id": r.row_id,
                "table_id": r.table_id,
                "row_index": r.row_index,
                "warnings": r.warnings
            })

    # 2. Run All Detectors
    pce_findings = run_pce_consistency_check(pv_rows, pce_tolerance_abs, pce_tolerance_rel)
    eqe_findings = run_eqe_jv_jsc_consistency_check(pv_rows, eqe_jsc_tolerance_rel, eqe_jsc_tolerance_abs)
    voc_findings = run_voc_loss_check(pv_rows)
    reporting_findings = run_pv_reporting_completeness_check(pv_rows)
    stability_findings = run_pv_stability_reporting_check(pv_rows)
    tandem_findings = run_tandem_consistency_check(pv_rows)
    materials_findings = run_materials_characterization_check(pv_rows)

    # Merge all findings and assign sequential global finding IDs
    all_findings_raw = (
        pce_findings + eqe_findings + voc_findings + 
        reporting_findings + stability_findings + 
        tandem_findings + materials_findings
    )

    final_findings = []
    finding_idx = 1
    for f in all_findings_raw:
        # Re-assign sequential ID
        f.finding_id = f"PV-FIND-{finding_idx:03d}"
        final_findings.append(f)
        finding_idx += 1

    # 3. Write outputs
    metric_rows_path = resolved_out / "pv_metric_rows.jsonl"
    field_mapping_path = resolved_out / "pv_field_mapping.jsonl"
    row_warnings_path = resolved_out / "pv_row_warnings.jsonl"
    findings_path = resolved_out / "pv_findings.jsonl"
    summary_path = resolved_out / "pv_domain_summary.md"

    _write_jsonl(metric_rows_path, [r.to_dict() for r in pv_rows])
    _write_jsonl(field_mapping_path, mappings_records)
    _write_jsonl(row_warnings_path, warnings_records)
    _write_jsonl(findings_path, [f.to_dict() for f in final_findings])

    # 4. Generate summary MD
    _generate_summary_report(
        summary_path,
        manifest_path,
        len(pv_rows),
        mappings_records,
        final_findings
    )

    return metric_rows_path, field_mapping_path, findings_path, summary_path

def _generate_summary_report(
    summary_path: Path,
    manifest_path: Path,
    total_rows: int,
    mappings: list[dict],
    findings: list[PVConsistencyFinding]
) -> None:
    # Separate findings by rule/type
    pce_f = [f for f in findings if f.rule_id == "pv_pce_consistency"]
    eqe_f = [f for f in findings if f.rule_id == "pv_eqe_jv_jsc_consistency"]
    voc_f = [f for f in findings if f.rule_id == "pv_voc_loss_consistency"]
    rep_f = [f for f in findings if f.rule_id == "pv_reporting_completeness"]
    stab_f = [f for f in findings if f.rule_id == "pv_stability_reporting_completeness"]
    tan_f = [f for f in findings if f.rule_id == "pv_tandem_current_matching"]
    mat_f = [f for f in findings if f.rule_id == "pv_materials_characterization_metadata"]

    lines = [
        "# Photovoltaics & Materials Domain Review Summary",
        "",
        "## Input Configurations",
        f"- Table Manifest: `{manifest_path.as_posix()}`",
        f"- Total parsed PV metric rows: {total_rows}",
        f"- Total column field mappings: {len(mappings)}",
        "",
        "## Field Mapping Summary",
    ]

    if mappings:
        for m in mappings:
            hint = f" ({m['mapping']['unit_hint']})" if m['mapping']['unit_hint'] else ""
            lines.append(
                f"- Table `{m['table_id']}` | Column `{m['column']}` -> Canonical `{m['mapping']['canonical_field']}`{hint} | Confidence: {m['mapping']['confidence']:.2f}"
            )
    else:
        lines.append("- No canonical PV column field mappings identified.")

    lines.extend([
        "",
        "## Findings Summary",
        f"- PCE Consistency findings: {len(pce_f)}",
        f"- EQE/J–V current-density findings: {len(eqe_f)}",
        f"- Voc loss / bandgap physical findings: {len(voc_f)}",
        f"- Solar cell reporting completeness gaps: {len(rep_f)}",
        f"- Stability reporting gaps: {len(stab_f)}",
        f"- Tandem PV consistency findings: {len(tan_f)}",
        f"- Materials characterization metadata gaps: {len(mat_f)}",
        "",
    ])

    def add_section(title, findings_list):
        lines.append(f"### {title}")
        if findings_list:
            for f in findings_list:
                row_str = f" (Row {f.row_index})" if f.row_index else ""
                device_str = f" (Device: {f.device_id})" if f.device_id else ""
                lines.append(f"- **{f.finding_id}** ({f.risk_level}): File `{f.source_file}`{row_str}{device_str}")
                lines.append(f"  - *Safe Language:* {f.safe_report_language}")
        else:
            lines.append("- No findings in this category.")
        lines.append("")

    add_section("PCE Consistency Findings", pce_f)
    add_section("EQE/J–V Current-Density Findings", eqe_f)
    add_section("Voc Loss / Bandgap Findings", voc_f)
    add_section("Solar Cell Reporting Completeness Gaps", rep_f)
    add_section("Stability Reporting Gaps", stab_f)
    add_section("Tandem PV Consistency Findings", tan_f)
    add_section("Materials Characterization Metadata Gaps", mat_f)

    # Gather verification questions and alternative explanations
    alts = sorted(list(set(alt for f in findings for alt in f.alternative_explanations)))
    mvs = sorted(list(set(mv for f in findings for mv in f.manual_verification)))

    lines.extend([
        "## Alternative Benign Explanations",
    ])
    if alts:
        for alt in alts:
            lines.append(f"- {alt}")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Manual Verification Checklist & Questions",
    ])
    if mvs:
        for mv in mvs:
            lines.append(f"- {mv}")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Limitations",
        "- Checks are restricted to parsed tabular source data and do not verify manuscript text, images, or raw binary instrument log formats directly.",
        "- Field mapping relies on header text matches and can fail on highly customized or non-English spreadsheets.",
        "",
        "## Do-not-overclaim notice",
        "- **These checks report domain-specific consistency and reporting signals only.**",
        "- **They do not determine data fabrication or research misconduct.**",
        "- **Missing fields may be present in manuscript text, figure captions, supplementary information, or raw data not included in this table package.**",
        "- **Numeric inconsistencies require raw data, formulas, units, and measurement protocols for verification.**",
        ""
    ])

    summary_path.write_text("\n".join(lines), encoding="utf-8")
