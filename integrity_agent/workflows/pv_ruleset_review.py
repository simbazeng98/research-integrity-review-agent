from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from integrity_agent.domains.photovoltaics.schema import build_pv_metric_rows, PVMetricRow
from integrity_agent.domains.photovoltaics.evidence_ruleset_v1 import TAXONOMY_RULESET, TaxonomyItem
from integrity_agent.core.path_display import display_path
from integrity_agent.core.evidence.ledger_schema import EvidenceRecord

def is_evidence_present(req: str, t_rows: list[PVMetricRow]) -> bool:
    # 1. Check if req is a canonical field name of PVMetricRow
    # and if any row has a non-None value for it
    if hasattr(t_rows[0], req):
        if any(getattr(r, req, None) is not None for r in t_rows):
            return True

    # 2. Check if req is present in the raw_values keys (headers) of the first row
    # using some standard string matching (e.g., exact lower match or partial match)
    headers = [k.lower() for k in t_rows[0].raw_values.keys()]
    req_lower = req.lower()

    # Check exact match in headers
    if req_lower in headers:
        if any(r.raw_values.get(k) is not None and str(r.raw_values.get(k)).strip() != ""
               for r in t_rows for k in r.raw_values.keys() if k.lower() == req_lower):
            return True

    # Also check if req matches mapped canonical fields or check partial match/custom aliases
    aliases = {
        "eqe_spectrum_range": ["eqe_range", "wavelength", "nm", "spectral range"],
        "am15g_reference_standard": ["am1.5", "reference", "standard", "astm", "iec"],
        "reflection_correction_applied": ["reflection", "correction", "reflectance"],
        "uv_exposure_dose": ["uv", "dose", "exposure"],
        "stability_tracking_mode": ["tracking", "shelf", "continuous", "storage"],
        "spectral_mismatch_factor": ["mismatch", "smf", "calibration"],
        "shadow_mask_present": ["shadow", "mask", "aperture"],
        "connection_type": ["connection", "2t", "4t", "terminal"],
        "chemical_composition": ["composition", "stoichiometry", "halide", "ratio"],
        "interface_treatment": ["interface", "sam", "passivation", "treatment"],
        "deposition_damage_mitigation": ["sputter", "ald", "damage", "buffer"],
        "materials_characterization_metadata": ["metadata", "xrd", "sem", "pl", "ups", "xps"],
    }

    if req_lower in aliases:
        for alias in aliases[req_lower]:
            for h in headers:
                if alias in h:
                    if any(r.raw_values.get(k) is not None and str(r.raw_values.get(k)).strip() != ""
                           for r in t_rows for k in r.raw_values.keys() if k.lower() == h):
                        return True

    # Let's also check if any header contains the required evidence name as a substring
    for h in headers:
        if h in req_lower or req_lower in h:
            if any(r.raw_values.get(k) is not None and str(r.raw_values.get(k)).strip() != ""
                   for r in t_rows for k in r.raw_values.keys() if k.lower() == h):
                return True

    return False

def _generate_review_summary_md(
    path: Path,
    total_tables: int,
    total_tables_with_pv: int,
    findings: list[EvidenceRecord],
    input_path: Path,
) -> None:
    # Clean input display path to avoid leaking absolute local paths
    input_display = display_path(input_path)
    for forbidden in ["D:", "C:", "file:///", "\\"]:
        if forbidden in input_display:
            input_display = input_path.name
            break

    lines = [
        "# PV Evidence Ruleset Review Summary",
        "",
        "> [!IMPORTANT]",
        "> **Safety Notice & Disclaimer**",
        "> - The PV evidence ruleset is a taxonomy of evidence completeness and consistency signals, **not an automatic misconduct detector**.",
        "> - Surfaced signals do **not** confirm, verify, or prove research misconduct, data fabrication, or fraud.",
        "> - Surfaced signals require **manual verification** and thorough **source/raw data** review to determine validity.",
        "",
        "## Statistics",
        f"- **Input path**: `{input_display}`",
        f"- **Total tables reviewed**: {total_tables}",
        f"- **Total tables with PV metadata**: {total_tables_with_pv}",
        f"- **Total completeness findings detected**: {len(findings)}",
        "",
        "## Detected Completeness Findings",
        ""
    ]

    if findings:
        for f in findings:
            source = f.evidence[0].source if f.evidence else "Unknown"
            location = f.evidence[0].location if f.evidence else "Unknown"
            lines.extend([
                f"### Finding: {f.finding_id} ({f.risk_level.upper()})",
                f"- **Rule ID**: `{f.rule_id}`",
                f"- **Source file**: `{source}`",
                f"- **Location**: `{location}`",
                f"- **Safe Report Language**: {f.safe_report_language}",
                "",
                "#### Manual Verification questions",
            ])
            for q in f.manual_verification.requests:
                lines.append(f"- {q}")

            lines.extend([
                "",
                "#### Benign Alternatives",
            ])
            for alt in f.alternative_explanations:
                lines.append(f"- {alt.get('text') if isinstance(alt, dict) else alt}")

            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("- No completeness gaps detected.")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

def run_pv_ruleset_review(
    input_path: Path | str,
    column_profiles_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    table_base_dir: Path | str | None = None,
) -> tuple[Path, Path, int]:
    input_path = Path(input_path)

    if output_dir is None:
        out_path = Path("outputs") / "pv_ruleset_review"
    else:
        out_path = Path(output_dir)

    out_path.mkdir(parents=True, exist_ok=True)

    # Internal manifest to avoid leaking local paths or failing to find files
    manifest_path = input_path
    if input_path.is_dir():
        from integrity_agent.workflows.table_intake import run_table_intake
        manifest_jsonl, _, temp_profiles, _ = run_table_intake(input_path, output_dir=out_path)
        if column_profiles_path is None:
            column_profiles_path = temp_profiles

        base_dir = Path(table_base_dir) if table_base_dir is not None else input_path.parent

        internal_manifest_path = out_path / "internal_table_manifest.jsonl"
        with manifest_jsonl.open("r", encoding="utf-8") as f_in, internal_manifest_path.open("w", encoding="utf-8") as f_out:
            for line in f_in:
                if line.strip():
                    item_data = json.loads(line)
                    rel_path = item_data["relative_path"]
                    abs_path = (base_dir / rel_path).resolve()
                    item_data["relative_path"] = str(abs_path)
                    f_out.write(json.dumps(item_data) + "\n")
        manifest_path = internal_manifest_path
    else:
        # If it is a manifest file, resolve to absolute paths relative to manifest folder or table_base_dir
        base_dir = Path(table_base_dir) if table_base_dir is not None else input_path.parent
        internal_manifest_path = out_path / "internal_table_manifest.jsonl"
        with input_path.open("r", encoding="utf-8") as f_in, internal_manifest_path.open("w", encoding="utf-8") as f_out:
            for line in f_in:
                if line.strip():
                    item_data = json.loads(line)
                    rel_path = item_data["relative_path"]
                    p = Path(rel_path)
                    if not p.is_absolute():
                        abs_path = (base_dir / rel_path).resolve()
                        if not abs_path.exists():
                            abs_path = (input_path.parent / rel_path).resolve()
                        item_data["relative_path"] = str(abs_path)
                    f_out.write(json.dumps(item_data) + "\n")
        manifest_path = internal_manifest_path

    # Build PV Metric Rows
    pv_rows = build_pv_metric_rows(manifest_path, column_profiles_path)

    # Group rows by table_id
    tables_rows: dict[str, list[PVMetricRow]] = {}
    for row in pv_rows:
        tables_rows.setdefault(row.table_id, []).append(row)

    findings: list[EvidenceRecord] = []
    finding_idx = 1
    total_tables_with_pv = 0

    for table_id, t_rows in tables_rows.items():
        source_file = t_rows[0].source_file

        # Check if table has PV fields
        has_pv_fields = False
        for r in t_rows:
            if any(getattr(r, val, None) is not None for val in [
                "voc_v", "jsc_ma_cm2", "ff", "pce_percent",
                "eqe_jsc_ma_cm2", "bandgap_ev", "active_area_cm2", "aperture_area_cm2",
                "stabilized_pce_percent", "stabilized_power_output_percent",
                "reverse_scan_pce_percent", "forward_scan_pce_percent",
                "scan_direction", "scan_rate", "active_area_cm2",
                "aperture_area_cm2", "mask_area_cm2", "light_intensity_mw_cm2",
                "temperature_c", "humidity_percent", "encapsulation",
                "mpp_tracking", "t80_h", "isos_protocol"
            ]):
                has_pv_fields = True
                break

        if not has_pv_fields:
            continue

        total_tables_with_pv += 1

        # Check each rule
        for item in TAXONOMY_RULESET:
            missing_evidence = []
            for req in item.required_evidence:
                if not is_evidence_present(req, t_rows):
                    missing_evidence.append(req)

            if missing_evidence:
                safe_lang = item.safe_report_language
                if item.risk_ceiling == "high":
                    if "raw/source-data" not in safe_lang.lower() and "source/raw data" not in safe_lang.lower():
                        safe_lang = safe_lang.rstrip(".") + " Warning: A high-risk rating for physical inconsistencies is subject to missing raw/source-data verification caveats; manual review of original spectral files and simulator calibration is required."

                # Ensure no absolute paths in source file name
                src_display = Path(source_file).name

                record = EvidenceRecord(
                    finding_id=f"PV-RULESET-FIND-{finding_idx:03d}",
                    finding_category="pv_evidence_completeness",
                    type=item.rule_id,
                    title=f"Missing PV Evidence: {item.rule_id}",
                    summary=safe_lang,
                    risk=item.risk_ceiling,
                    risk_level=item.risk_ceiling,
                    needs_manual_review=True,
                    evidence=[
                        {
                            "source": src_display,
                            "location": f"Table {table_id}",
                        }
                    ],
                    manual_verification={
                        "needed": True,
                        "requests": item.manual_verification_questions,
                    },
                    false_positive_risks=item.false_positive_risks,
                    benign_alternatives=[{"text": a} for a in item.benign_alternatives],
                    alternative_explanations=item.benign_alternatives,
                    limitations="Tabular completeness review is limited to parsed column headers.",
                    provenance={
                        "table_id": table_id,
                        "source_file": src_display,
                        "missing_fields": missing_evidence,
                    },
                    rule_id=item.rule_id,
                    safe_report_language=safe_lang,
                )
                findings.append(record)
                finding_idx += 1

    # Write findings.jsonl
    findings_file = out_path / "pv_ruleset_findings.jsonl"
    with findings_file.open("w", encoding="utf-8") as f:
        for finding in findings:
            f.write(finding.model_dump_json(by_alias=True) + "\n")

    # Generate summary report
    summary_file = out_path / "pv_ruleset_review_summary.md"
    _generate_review_summary_md(
        summary_file,
        total_tables=len(tables_rows),
        total_tables_with_pv=total_tables_with_pv,
        findings=findings,
        input_path=input_path,
    )

    # Remove internal manifest to avoid leaving temporary files with absolute paths
    if internal_manifest_path.exists():
        try:
            internal_manifest_path.unlink()
        except OSError:
            pass

    print(f"Wrote PV ruleset findings: {display_path(findings_file)}")
    print(f"Wrote PV ruleset review summary: {display_path(summary_file)}")

    return findings_file, summary_file, total_tables_with_pv
