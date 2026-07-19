from __future__ import annotations

import json
from pathlib import Path

from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.core.tables.table_schema import TableManifestItem, TableEvidenceFinding
from integrity_agent.detectors.numeric.fixed_delta import detect_fixed_delta
from integrity_agent.detectors.numeric.quantization_grid import detect_quantization_grid
from integrity_agent.detectors.numeric.terminal_digit import detect_terminal_digits

DEFAULT_OUTPUT_DIR = Path("outputs") / "table_intake"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _parse_columns_and_rows_from_loc(location: str) -> tuple[list[str], str]:
    cols = []
    row_range = "unknown"

    # Parse columns
    if "columns " in location:
        # e.g., "columns X and Y; rows 1-5"
        col_part = location.split(";")[0].replace("columns ", "").strip()
        cols = [c.strip() for c in col_part.split(" and ")]
    elif "column " in location:
        # e.g., "column Z; ..."
        col_part = location.split(";")[0].replace("column ", "").strip()
        cols = [col_part]
    elif "measurement column" in location:
        cols = ["measurement"]

    # Parse row range
    if "rows " in location:
        row_range = location.split("rows ")[-1].strip()
    elif "row " in location:
        row_range = location.split("row ")[-1].strip()

    return cols, row_range


def _generate_numeric_review_summary_md(
    path: Path,
    total_tables: int,
    findings: list[TableEvidenceFinding],
) -> None:
    lines = [
        "# Table Numeric Review Summary",
        "",
        "## Statistics",
        f"- Total tables reviewed: {total_tables}",
        f"- Total numeric findings detected: {len(findings)}",
        "",
        "## Detected Risk Findings",
    ]

    if findings:
        for f in findings:
            lines.append(
                f"- Finding `{f.finding_id}` ({f.rule_id} | {f.risk_level}):"
            )
            lines.append(f"  - File: `{f.source_file}` (Table: `{f.table_id}`)")
            lines.append(f"  - Columns: `{', '.join(f.column_names)}` | Rows: `{f.row_range}`")
            lines.append(f"  - Safe language: {f.safe_report_language}")
    else:
        lines.append("- No numeric risk findings detected.")

    # Gather distinct checklists/limitations
    alts = sorted(set(item for f in findings for item in f.alternative_explanations))
    fprs = sorted(set(item for f in findings for item in f.false_positive_risks))
    mvs = sorted(set(item for f in findings for item in f.manual_verification))

    lines.extend([
        "",
        "## Alternative Benign Explanations",
    ])
    if alts:
        for alt in alts:
            lines.append(f"- {alt}")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## False Positive Risks",
    ])
    if fprs:
        for fpr in fprs:
            lines.append(f"- {fpr}")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Manual Verification Checklist",
    ])
    if mvs:
        for mv in mvs:
            lines.append(f"- {mv}")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Limitations",
        "- Fixed delta checks identify constant differences between numeric columns, which can result from unit conversions or formula derivations.",
        "- Terminal digit checks flag concentration anomalies, but small sample sizes (under 15 values) can easily skew statistics.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate numeric risk signals for human review. It does not determine data fabrication, falsification, or research misconduct.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def run_table_numeric_review(
    manifest_jsonl_path: Path | str,
    output_dir: Path | str | None = None,
    table_base_dir: Path | str | None = None,
    column_profiles_path: Path | str | None = None,
) -> tuple[Path, Path]:
    """Execute v0.9 Table Numeric Review routing over a table manifest."""
    manifest_jsonl_path = Path(manifest_jsonl_path)
    if not manifest_jsonl_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_jsonl_path}")

    resolved_out = DEFAULT_OUTPUT_DIR if output_dir is None else Path(output_dir)
    resolved_out.mkdir(parents=True, exist_ok=True)

    # 1. Load manifest items
    items: list[TableManifestItem] = []
    with manifest_jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(TableManifestItem(**json.loads(line)))

    profiles_by_table: dict[str, dict[str, dict]] = {}
    if column_profiles_path is not None:
        profiles_path = Path(column_profiles_path)
        if profiles_path.exists():
            with profiles_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    table_id = record.get("table_id")
                    profile = record.get("profile")
                    if not table_id or not isinstance(profile, dict):
                        continue
                    column_name = profile.get("column_name")
                    if column_name:
                        profiles_by_table.setdefault(str(table_id), {})[
                            str(column_name)
                        ] = profile

    # 2. Load registry rules
    project_root = Path.cwd()
    base_dir = Path(table_base_dir) if table_base_dir is not None else project_root
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")

    rule_fd = registry.get("numeric_fixed_delta_between_columns")
    rule_td = registry.get("numeric_terminal_digit_anomaly")
    rule_qg = registry.get("measurement_precision_anomaly")

    findings: list[TableEvidenceFinding] = []
    finding_idx = 1

    # 3. Process each table item
    for item in items:
        # Resolve target table file path
        file_path = Path(item.relative_path)
        if not file_path.is_absolute():
            file_path = (base_dir / item.relative_path).resolve()

        if not file_path.exists():
            # Try prepending examples/toy_table_package
            fallback = (project_root / "examples" / "toy_table_package" / Path(item.relative_path).name).resolve()
            if fallback.exists():
                file_path = fallback
            else:
                raise FileNotFoundError(
                    f"Table manifest path could not be resolved: {item.relative_path}"
                )

        # Keep the public manifest relative, but pass the already-resolved path
        # to detector runtime so it does not resolve against Path.cwd().
        options = {
            "file_path": file_path,
            "sheet_name": item.sheet_name,
            "table_id": item.table_id,
            "profiles": profiles_by_table.get(item.table_id, {}),
        }

        # Run Domain Routing
        from integrity_agent.domains import route_table_columns
        matches = route_table_columns(item.columns)
        if matches and matches[0].score > 0:
            best_match = matches[0]
            finding = TableEvidenceFinding(
                finding_id=f"TBL-FIND-{finding_idx:03d}",
                rule_id=f"domain_routing_{best_match.domain_id}",
                risk_level="low",
                table_id=item.table_id,
                source_file=item.source_file,
                column_names=list(best_match.matched_fields.values()),
                row_range="all",
                safe_report_language=f"Table routed to domain '{best_match.domain_id}' (status: routing_only / not_implemented). Matched columns: {list(best_match.matched_fields.keys())}.",
                alternative_explanations=["Benign metadata match with domain schema templates without data issues."],
                false_positive_risks=["Columns match domain patterns by coincidence."],
                manual_verification=[f"Verify if the table metrics belong to domain '{best_match.domain_id}' and require domain-specific analysis."],
                metadata={
                    "domain_id": best_match.domain_id,
                    "score": best_match.score,
                    "matched_fields": best_match.matched_fields,
                    "status": "routing_only",
                    "not_implemented": True
                }
            )
            findings.append(finding)
            finding_idx += 1

        # Run Fixed Delta Detector
        if rule_fd:
            fd_results = detect_fixed_delta(file_path, rule_fd, options)
            for res in fd_results:
                cols, row_range = _parse_columns_and_rows_from_loc(res.evidence_items[0].get("location", ""))
                finding = TableEvidenceFinding(
                    finding_id=f"TBL-FIND-{finding_idx:03d}",
                    rule_id=res.rule_id,
                    risk_level=res.risk_level,
                    table_id=item.table_id,
                    source_file=item.source_file,
                    column_names=cols,
                    row_range=row_range,
                    safe_report_language=res.safe_report_language,
                    alternative_explanations=res.alternative_explanations,
                    false_positive_risks=res.false_positive_risks,
                    manual_verification=res.missing_verification_materials,
                    metadata=res.metadata,
                )
                findings.append(finding)
                finding_idx += 1

        # Run Terminal Digit Detector
        if rule_td:
            td_results = detect_terminal_digits(file_path, rule_td, options)
            for res in td_results:
                cols, row_range = _parse_columns_and_rows_from_loc(res.evidence_items[0].get("location", ""))
                finding = TableEvidenceFinding(
                    finding_id=f"TBL-FIND-{finding_idx:03d}",
                    rule_id=res.rule_id,
                    risk_level=res.risk_level,
                    table_id=item.table_id,
                    source_file=item.source_file,
                    column_names=cols,
                    row_range=row_range,
                    safe_report_language=res.safe_report_language,
                    alternative_explanations=res.alternative_explanations,
                    false_positive_risks=res.false_positive_risks,
                    manual_verification=res.missing_verification_materials,
                    metadata=res.metadata,
                )
                findings.append(finding)
                finding_idx += 1

        # Run quantization-grid detector using table-intake ColumnProfile data.
        if rule_qg:
            qg_results = detect_quantization_grid(file_path, rule_qg, options)
            for res in qg_results:
                cols, row_range = _parse_columns_and_rows_from_loc(
                    res.evidence_items[0].get("location", "")
                )
                finding = TableEvidenceFinding(
                    finding_id=f"TBL-FIND-{finding_idx:03d}",
                    rule_id=res.rule_id,
                    risk_level=res.risk_level,
                    table_id=item.table_id,
                    source_file=item.source_file,
                    column_names=cols,
                    row_range=row_range,
                    safe_report_language=res.safe_report_language,
                    alternative_explanations=res.alternative_explanations,
                    false_positive_risks=res.false_positive_risks,
                    manual_verification=res.missing_verification_materials,
                    metadata=res.metadata,
                )
                findings.append(finding)
                finding_idx += 1

    # 4. Write findings
    findings_jsonl = resolved_out / "table_numeric_findings.jsonl"
    _write_jsonl(findings_jsonl, [f.to_dict() for f in findings])

    # 5. Write summary report
    summary_md = resolved_out / "table_numeric_review_summary.md"
    _generate_numeric_review_summary_md(summary_md, len(items), findings)

    return findings_jsonl.resolve(), summary_md.resolve()
