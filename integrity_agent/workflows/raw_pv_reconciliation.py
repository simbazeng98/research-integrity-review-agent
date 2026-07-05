from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from integrity_agent.core.path_display import display_path
import sys

from integrity_agent.domains.photovoltaics.raw_measurements.schema import RawPVConsistencyFinding
from integrity_agent.workflows.raw_pv_intake import run_raw_pv_intake
from integrity_agent.workflows.jv_recalculate import run_jv_recalculate
from integrity_agent.workflows.eqe_recalculate import run_eqe_recalculate
from integrity_agent.workflows.excel_formula_audit import run_excel_formula_audit

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Coordinated raw measurement reconciliation workflow.")
    parser.add_argument("package_dir", help="Path to raw measurements package directory.")
    parser.add_argument("-o", "--output-dir", default="outputs/raw_pv", help="Directory for output files.")
    return parser.parse_args(args)

def run_raw_pv_reconciliation(package_dir: str, output_dir: str = "outputs/raw_pv") -> list[RawPVConsistencyFinding]:
    pack_path = Path(package_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    findings_file = out_path / "raw_pv_findings.jsonl"
    summary_file = out_path / "raw_pv_reconciliation_summary.md"

    # 1. Intake Manifest
    run_raw_pv_intake(package_dir, output_dir)

    # Resolve paths
    reported_file = None
    reported_dir = pack_path / "reported"
    if reported_dir.exists():
        for f in reported_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".csv", ".tsv"):
                reported_file = str(f)
                break

    reference_file = None
    reference_dir = pack_path / "reference"
    if reference_dir.exists():
        for f in reference_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".csv", ".tsv"):
                reference_file = str(f)
                break

    # 2. JV Recalculation
    jv_findings = []
    jv_folder = pack_path / "jv"
    if jv_folder.exists():
        jv_findings = run_jv_recalculate(
            jv_folder=str(jv_folder),
            reported_file=reported_file,
            output_dir=output_dir,
            pin=100.0
        )

    # 3. EQE Recalculation
    eqe_findings = []
    eqe_folder = pack_path / "eqe"
    if eqe_folder.exists():
        eqe_findings = run_eqe_recalculate(
            eqe_folder=str(eqe_folder),
            reference_file=reference_file,
            reported_file=reported_file,
            jv_metrics_file=str(out_path / "jv_metrics.jsonl"),
            output_dir=output_dir
        )

    # 4. Excel Audit
    excel_findings = []
    excel_folder = pack_path / "excel"
    if excel_folder.exists():
        excel_findings = run_excel_formula_audit(
            excel_folder=str(excel_folder),
            output_dir=output_dir
        )

    # Combine all findings
    all_findings = jv_findings + eqe_findings + excel_findings

    # Write combined findings to raw_pv_findings.jsonl
    with findings_file.open("w", encoding="utf-8") as f:
        for finding in all_findings:
            f.write(json.dumps(finding.to_dict()) + "\n")

    # Group findings for summary
    jv_recalc = [f for f in all_findings if f.rule_id == "pv_jv_metric_recalculation"] # None directly, but we have hysteresis or source rec
    jv_hyst = [f for f in all_findings if f.rule_id == "pv_jv_hysteresis_candidate"]
    eqe_int = [f for f in all_findings if f.rule_id == "pv_eqe_spectrum_integration"]
    excel_audit = [f for f in all_findings if f.rule_id == "pv_excel_formula_audit"]
    source_rec = [f for f in all_findings if f.rule_id == "pv_source_reconciliation"]

    # Generate summary MD
    summary_lines = [
        "# Raw PV Reconciliation Summary",
        "",
        f"- **Raw measurement package directory**: `{package_dir}`",
        f"- **Total recomputed findings**: {len(all_findings)}",
        "",
        "## Summary of Findings by Category",
        f"- **J–V hysteresis candidate signals**: {len(jv_hyst)}",
        f"- **EQE spectrum integration signals**: {len(eqe_int)}",
        f"- **Excel formula audit signals**: {len(excel_audit)}",
        f"- **Cross-source reconciliation signals**: {len(source_rec)}",
        "",
        "## Manual Verification Checklist",
        "- Obtain original unprocessed instrument sweep text files (forward and reverse direction) to check scan delay.",
        "- Verify whether reported summary values correspond to champion device dynamic scan or stabilized MPP tracking.",
        "- Check the reference diode calibration certificate and spectral mismatch correction logs.",
        "- Trace Excel formulas to ensure no intermediate results are hardcoded in summary columns.",
        "- Seek clarification from the authors on naming/device ID mapping configurations.",
        "",
        "## Limitations",
        "- Simple linear interpolation is applied at zero-crossing regions, which can deviate from local curve fitting under high noise.",
        "- Excel formula audit does not execute the full Excel workbook calculation engine.",
        "- Cross-source reconciliation relies on exact or heuristic device ID matches which can be ambiguous.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate consistency, integration, and formula audit signals for human review. It does not determine data fabrication or research misconduct."
    ]

    summary_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Wrote consolidated raw PV findings: {display_path(findings_file)}")
    print(f"Wrote unified raw PV reconciliation summary: {display_path(summary_file)}")

    return all_findings

def main(args=None):
    parsed = parse_args(args)
    run_raw_pv_reconciliation(parsed.package_dir, parsed.output_dir)

if __name__ == "__main__":
    main()
