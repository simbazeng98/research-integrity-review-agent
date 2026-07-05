from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from integrity_agent.core.path_display import display_path
import sys

from integrity_agent.domains.photovoltaics.raw_measurements.schema import ExcelFormulaAuditItem, RawPVConsistencyFinding
from integrity_agent.domains.photovoltaics.raw_measurements.excel_formula_audit import audit_excel_formulas

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Audit Excel spreadsheets for formula and hardcoding anomalies.")
    parser.add_argument("excel_folder", help="Directory containing Excel spreadsheet files.")
    parser.add_argument("-o", "--output-dir", default="outputs/raw_pv", help="Directory for output files.")
    return parser.parse_args(args)

def run_excel_formula_audit(excel_folder: str, output_dir: str = "outputs/raw_pv") -> list[RawPVConsistencyFinding]:
    excel_path = Path(excel_folder)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    audit_file = out_path / "excel_formula_audit.jsonl"
    summary_file = out_path / "excel_formula_audit_summary.md"

    # Find spreadsheet files (.xlsx, .xlsm)
    excel_files = []
    if excel_path.exists():
        if excel_path.is_file():
            excel_files = [excel_path]
        else:
            for root, _, files in os.walk(excel_path):
                for f in files:
                    if Path(f).suffix.lower() in (".xlsx", ".xlsm"):
                        excel_files.append(Path(root) / f)

    all_audit_items: list[ExcelFormulaAuditItem] = []
    
    for xl_f in excel_files:
        items = audit_excel_formulas(str(xl_f))
        all_audit_items.extend(items)

    # Convert to RawPVConsistencyFinding objects
    findings = []
    finding_counter = 1

    for item in all_audit_items:
        # We only generate findings for interesting checks (exclude plain formula_cell and load_error)
        if item.audit_type in ("formula_cell", "load_error"):
            continue
            
        risk_level = "medium" if item.severity == "medium" else "low"
        
        # Build safe report language based on audit type
        safe_lang = ""
        if item.audit_type == "hardcoded_output":
            safe_lang = (
                f"Candidate spreadsheet formula audit signal: hardcoded cell '{item.cell_coordinate}' containing "
                f"numeric value '{item.cell_value}' was found in a row/column of sheet '{item.sheet_name}' otherwise populated by formulas. "
                f"Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )
        elif item.audit_type == "formula_overwrite_pattern":
            safe_lang = (
                f"Candidate spreadsheet formula audit signal: hardcoded numeric cell '{item.cell_coordinate}' "
                f"value '{item.cell_value}' found under calculated column header in sheet '{item.sheet_name}'. "
                f"Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )
        elif item.audit_type == "formula_value_mismatch":
            safe_lang = (
                f"Candidate spreadsheet formula audit signal: {item.message} "
                f"Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )
        elif item.audit_type == "volatile_function":
            safe_lang = (
                f"Candidate spreadsheet formula audit signal: volatile function '{item.formula}' detected in cell '{item.cell_coordinate}' "
                f"of sheet '{item.sheet_name}'. Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )
        elif item.audit_type == "external_reference":
            safe_lang = (
                f"Candidate spreadsheet formula audit signal: external reference '{item.formula}' detected in cell '{item.cell_coordinate}' "
                f"of sheet '{item.sheet_name}'. Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )
        elif item.audit_type == "xlsm_not_supported_for_formula_audit_safety":
            safe_lang = (
                f"Spreadsheet formula audit safety warning: macro-enabled workbook (.xlsm) is not supported for formula audit safety. "
                f"Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )
        else:
            safe_lang = (
                f"Candidate spreadsheet formula audit signal: parsed pattern in sheet '{item.sheet_name}' cell '{item.cell_coordinate}' "
                f"may require verification. Verify spreadsheet formulas, raw data provenance, and analysis workflow."
            )

        findings.append(RawPVConsistencyFinding(
            finding_id=f"RAW-PV-FIND-EXCEL-{finding_counter:03d}",
            rule_id="pv_excel_formula_audit",
            detector_id="excel_formula_auditor",
            risk_level=risk_level,
            risk_ceiling="medium",
            source_file=item.source_file,
            device_id=None,
            observed_values={
                "sheet_name": item.sheet_name,
                "cell_coordinate": item.cell_coordinate,
                "cell_value": item.cell_value,
                "formula": item.formula,
                "audit_type": item.audit_type
            },
            recomputed_values={
                "cached_value": item.cached_value
            },
            tolerance=None,
            evidence_items=[{
                "location": f"Sheet '{item.sheet_name}' / Cell {item.cell_coordinate}",
                "message": item.message
            }],
            safe_report_language=safe_lang,
            alternative_explanations=[
                "intentionally pasted final values",
                "formula not preserved after export",
                "Excel cached values not available",
                "workbook generated by instrument software",
                "formula evaluator limitation",
                "copied summary table",
                "legitimate external linked workbook"
            ],
            false_positive_risks=[
                "Standard copying/pasting of metrics to summary tab",
                "Legitimate manual entry of baseline constants",
                "Parser unable to parse complicated nested Excel formulas"
            ],
            manual_verification=[
                "original workbook",
                "formula-preserving workbook",
                "raw instrument exports",
                "analysis script",
                "author explanation",
                "version history if available"
            ],
            limitations=[
                "Does not execute full Excel calculation engine"
            ],
            metadata={
                "audit_type": item.audit_type,
                "cell_coordinate": item.cell_coordinate
            }
        ))
        finding_counter += 1

    # Write items
    with audit_file.open("w", encoding="utf-8") as f:
        for item in all_audit_items:
            f.write(json.dumps(item.to_dict()) + "\n")

    # Generate summary MD
    scanned_filenames = [f.name for f in excel_files]
    formula_count = sum(1 for item in all_audit_items if item.audit_type == "formula_cell")
    hc_count = sum(1 for item in all_audit_items if item.audit_type == "hardcoded_output")
    ext_count = sum(1 for item in all_audit_items if item.audit_type == "external_reference")
    vol_count = sum(1 for item in all_audit_items if item.audit_type == "volatile_function")
    mismatch_count = sum(1 for item in all_audit_items if item.audit_type == "formula_value_mismatch")
    
    hidden_sheets = sum(1 for item in all_audit_items if item.audit_type == "hidden_sheet")
    hidden_rows = sum(1 for item in all_audit_items if item.audit_type == "hidden_row")
    hidden_cols = sum(1 for item in all_audit_items if item.audit_type == "hidden_column")
    
    summary_lines = [
        "# Excel Formula Audit Summary",
        "",
        f"- **Workbooks Scanned**: {len(excel_files)} (`{', '.join(scanned_filenames)}`)",
        f"- **Formula cells found**: {formula_count}",
        f"- **Hardcoded output candidates**: {hc_count}",
        f"- **External references**: {ext_count}",
        f"- **Volatile formulas**: {vol_count}",
        f"- **Formula value mismatches**: {mismatch_count}",
        f"- **Hidden sheets/rows/columns**: {hidden_sheets} sheets, {hidden_rows} rows, {hidden_cols} columns",
        "",
        "## Manual Verification Checklist",
        "- Open the original workbook in Microsoft Excel or LibreOffice.",
        "- Trace formulas and verify if intermediate outputs are hardcoded.",
        "- Request the original formula-preserving workbook if a values-only copy was supplied.",
        "- Review linked external files or databases referenced by formulas.",
        "",
        "## Limitations",
        "- Excel formula parsing is limited to cell reference arithmetic and basic operators.",
        "- Macro execution and external workbook values are not loaded or validated for security reasons.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate spreadsheet formula audit signals for human review. It does not determine data fabrication or research misconduct."
    ]

    summary_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Wrote Excel formula audit log: {display_path(audit_file)}")
    print(f"Wrote Excel formula audit summary: {display_path(summary_file)}")

    return findings

def main(args=None):
    parsed = parse_args(args)
    run_excel_formula_audit(parsed.excel_folder, parsed.output_dir)

if __name__ == "__main__":
    main()
