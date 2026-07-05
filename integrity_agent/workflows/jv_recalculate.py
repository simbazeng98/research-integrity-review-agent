from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from integrity_agent.core.path_display import display_path
import sys

from integrity_agent.domains.photovoltaics.raw_measurements.schema import JVCurve, JVMetrics, RawPVConsistencyFinding
from integrity_agent.domains.photovoltaics.raw_measurements.jv_curve_reader import read_jv_curve_file
from integrity_agent.domains.photovoltaics.raw_measurements.jv_metrics import extract_jv_metrics
from integrity_agent.domains.photovoltaics.raw_measurements.jv_hysteresis import pair_forward_reverse_curves, run_jv_hysteresis_check
from integrity_agent.domains.photovoltaics.raw_measurements.source_reconciliation import reconcile_jv_metrics_with_reported
from integrity_agent.domains.photovoltaics.field_mapping import infer_pv_field_mapping
from integrity_agent.domains.photovoltaics.units import (
    normalize_voc, normalize_jsc, normalize_ff, normalize_pce
)
from integrity_agent.domains.photovoltaics.schema import PVMetricRow

def load_reported_metrics_csv(path: str) -> list[PVMetricRow]:
    filepath = Path(path)
    if not filepath.exists():
        print(f"WARNING: Reported file '{path}' not found.", file=sys.stderr)
        return []

    rows = []
    try:
        # Read delimiter
        delim = ","
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            first_line = f.readline()
            if "\t" in first_line:
                delim = "\t"

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f, delimiter=delim)
            headers = next(reader, None)
            if not headers:
                return []
            
            # Map headers
            col_mappings = {}
            for idx, h in enumerate(headers):
                m = infer_pv_field_mapping(h)
                if m:
                    col_mappings[m.canonical_field] = (idx, m.unit_hint)

            row_counter = 1
            for row in reader:
                if not row or all(not cell.strip() for cell in row):
                    continue
                    
                # Extract values
                voc_idx, voc_uh = col_mappings.get("voc_v", (None, None))
                jsc_idx, jsc_uh = col_mappings.get("jsc_ma_cm2", (None, None))
                ff_idx, ff_uh = col_mappings.get("ff", (None, None))
                pce_idx, pce_uh = col_mappings.get("pce_percent", (None, None))
                eqe_idx, eqe_uh = col_mappings.get("eqe_jsc_ma_cm2", (None, None))
                
                # Device ID
                device_id = None
                for idx, h in enumerate(headers):
                    if "device" in h.lower() or "id" in h.lower():
                        device_id = row[idx]
                        break
                if not device_id:
                    device_id = row[0] if row else f"row-{row_counter}"

                # Normalizations
                voc_val = None
                if voc_idx is not None and voc_idx < len(row):
                    try:
                        v = float(row[voc_idx])
                        voc_val, _ = normalize_voc(v, voc_uh)
                    except ValueError:
                        pass

                jsc_val = None
                if jsc_idx is not None and jsc_idx < len(row):
                    try:
                        v = float(row[jsc_idx])
                        jsc_val, _ = normalize_jsc(v, jsc_uh)
                    except ValueError:
                        pass

                ff_val = None
                if ff_idx is not None and ff_idx < len(row):
                    try:
                        v = float(row[ff_idx])
                        ff_val, _, _ = normalize_ff(v, ff_uh)
                    except ValueError:
                        pass

                pce_val = None
                if pce_idx is not None and pce_idx < len(row):
                    try:
                        v = float(row[pce_idx])
                        pce_val, _ = normalize_pce(v, pce_uh)
                    except ValueError:
                        pass

                eqe_val = None
                if eqe_idx is not None and eqe_idx < len(row):
                    try:
                        v = float(row[eqe_idx])
                        eqe_val = v  # raw eqe current
                    except ValueError:
                        pass

                raw_vals = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}

                rows.append(PVMetricRow(
                    row_id=f"{filepath.stem}-row-{row_counter}",
                    source_file=filepath.name,
                    table_id=filepath.stem,
                    row_index=row_counter,
                    device_id=device_id,
                    voc_v=voc_val,
                    jsc_ma_cm2=jsc_val,
                    ff=ff_val,
                    pce_percent=pce_val,
                    eqe_jsc_ma_cm2=eqe_val,
                    raw_values=raw_vals
                ))
                row_counter += 1
    except Exception as e:
        print(f"WARNING: Failed to parse reported file '{path}': {e}", file=sys.stderr)

    return rows

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Recalculate metrics from raw J–V sweep files.")
    parser.add_argument("jv_folder", help="Directory containing raw J–V sweep files.")
    parser.add_argument("--reported", help="Optional reported metrics CSV file to reconcile.")
    parser.add_argument("-o", "--output-dir", default="outputs/raw_pv", help="Directory for output files.")
    parser.add_argument("--pin", type=float, default=100.0, help="Light intensity in mW/cm2.")
    return parser.parse_args(args)

def run_jv_recalculate(jv_folder: str, reported_file: str | None = None, output_dir: str = "outputs/raw_pv", pin: float = 100.0) -> list[RawPVConsistencyFinding]:
    jv_path = Path(jv_folder)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    curves_file = out_path / "jv_curves.jsonl"
    metrics_file = out_path / "jv_metrics.jsonl"
    hysteresis_file = out_path / "jv_hysteresis_findings.jsonl"
    reconciliation_file = out_path / "jv_reconciliation_findings.jsonl"
    summary_file = out_path / "jv_recalculation_summary.md"

    # Find raw JV files (.csv, .tsv, .txt)
    jv_files = []
    if jv_path.exists():
        if jv_path.is_file():
            jv_files = [jv_path]
        else:
            for root, _, files in os.walk(jv_path):
                for f in files:
                    if Path(f).suffix.lower() in (".csv", ".tsv", ".txt"):
                        jv_files.append(Path(root) / f)

    # Read curves and extract metrics
    curves = []
    metrics_list = []
    curves_warnings_count = 0

    for jv_f in jv_files:
        curve = read_jv_curve_file(str(jv_f))
        curves.append(curve)
        if curve.warnings:
            curves_warnings_count += 1
            
        metrics = extract_jv_metrics(curve, pin)
        metrics_list.append(metrics)

    # Pair and run hysteresis
    pairs = pair_forward_reverse_curves(curves, metrics_list)
    hysteresis_findings = run_jv_hysteresis_check(pairs)

    # Reconciliation
    reconciliation_findings = []
    reported_rows = []
    if reported_file:
        reported_rows = load_reported_metrics_csv(reported_file)
        reconciliation_findings = reconcile_jv_metrics_with_reported(metrics_list, reported_rows)

    # Write files
    with curves_file.open("w", encoding="utf-8") as f:
        for c in curves:
            f.write(json.dumps(c.to_dict()) + "\n")

    with metrics_file.open("w", encoding="utf-8") as f:
        for m in metrics_list:
            f.write(json.dumps(m.to_dict()) + "\n")

    with hysteresis_file.open("w", encoding="utf-8") as f:
        for h in hysteresis_findings:
            f.write(json.dumps(h.to_dict()) + "\n")

    with reconciliation_file.open("w", encoding="utf-8") as f:
        for r in reconciliation_findings:
            f.write(json.dumps(r.to_dict()) + "\n")

    # Generate summary MD
    summary_lines = [
        "# J–V Recalculation Summary",
        "",
        f"- **Input Folder**: `{jv_folder}`",
        f"- **Number of curves parsed**: {len(curves)}",
        f"- **Number of metrics extracted**: {len(metrics_list)}",
        f"- **Curves with warnings**: {curves_warnings_count}",
        f"- **Hysteresis candidate signals**: {len(hysteresis_findings)}",
        f"- **Reported metric reconciliation signals**: {len(reconciliation_findings)}",
        "",
        "## Manual Verification Checklist",
        "- Retrieve and inspect raw forward/reverse J–V sweep text files.",
        "- Verify whether reported summary values correspond to forward scan, reverse scan, or stabilized MPP tracking.",
        "- Review instrument measurement logs for preconditioning delays, scan rate, and aperture mask dimensions.",
        "- Confirm the solar simulator calibration and light intensity logs on the day of measurement.",
        "",
        "## Limitations",
        "- Interpolation at Voc/Jsc uses simple linear fit which can deviate slightly from polynomial fits on noisy sweeps.",
        "- Hysteresis pairing relies on filename heuristics or device ID metadata.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate consistency and hysteresis signals for human review. It does not determine data fabrication or research misconduct."
    ]

    summary_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Wrote J-V curves: {display_path(curves_file)}")
    print(f"Wrote J-V metrics: {display_path(metrics_file)}")
    print(f"Wrote J-V hysteresis findings: {display_path(hysteresis_file)}")
    print(f"Wrote J-V reconciliation findings: {display_path(reconciliation_file)}")
    print(f"Wrote J-V recalculation summary: {display_path(summary_file)}")

    return hysteresis_findings + reconciliation_findings

def main(args=None):
    parsed = parse_args(args)
    run_jv_recalculate(parsed.jv_folder, parsed.reported, parsed.output_dir, parsed.pin)

if __name__ == "__main__":
    main()
