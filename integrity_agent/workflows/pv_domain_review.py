from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from integrity_agent.core.tables.table_schema import TableManifestItem
from integrity_agent.domains.photovoltaics.schema import build_pv_metric_rows, PVMetricRow, PVConsistencyFinding
from integrity_agent.domains.photovoltaics.field_mapping import infer_pv_field_mapping
from integrity_agent.domains.photovoltaics.pce_consistency import run_pce_consistency_check
from integrity_agent.domains.photovoltaics.eqe_jv_consistency import run_eqe_jv_jsc_consistency_check
from integrity_agent.domains.photovoltaics.voc_loss import run_voc_loss_check
from integrity_agent.domains.photovoltaics.reporting_completeness import run_pv_reporting_completeness_check
from integrity_agent.domains.photovoltaics.stability_reporting import run_pv_stability_reporting_check
from integrity_agent.domains.photovoltaics.tandem_consistency import run_tandem_consistency_check
from integrity_agent.domains.photovoltaics.materials_characterization import run_materials_characterization_check

DEFAULT_OUTPUT_DIR = Path("outputs") / "pv_domain"

def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def run_pv_domain_review(
    manifest_path: Path | str,
    column_profiles_path: Path | str | None = None,
    output_dir: Path | str | None = None,
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
    pv_rows = build_pv_metric_rows(manifest_path, column_profiles_path)

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
