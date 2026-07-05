from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from integrity_agent.core.path_display import display_path
import sys

from integrity_agent.domains.photovoltaics.raw_measurements.schema import EQESpectrum, EQEIntegrationResult, JVMetrics, RawPVConsistencyFinding
from integrity_agent.domains.photovoltaics.raw_measurements.eqe_spectrum_reader import read_eqe_spectrum_file
from integrity_agent.domains.photovoltaics.raw_measurements.am15g_reference import load_reference_spectrum
from integrity_agent.domains.photovoltaics.raw_measurements.eqe_integration import integrate_eqe_jsc
from integrity_agent.domains.photovoltaics.raw_measurements.source_reconciliation import reconcile_eqe_with_reported, reconcile_eqe_with_jv
from integrity_agent.workflows.jv_recalculate import load_reported_metrics_csv

def load_jv_metrics_jsonl(path: str) -> list[JVMetrics]:
    filepath = Path(path)
    if not filepath.exists():
        print(f"WARNING: J-V metrics file '{path}' not found.", file=sys.stderr)
        return []
    metrics = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    metrics.append(JVMetrics(
                        curve_id=d.get("curve_id", ""),
                        device_id=d.get("device_id", ""),
                        voc_v=d.get("voc_v"),
                        jsc_ma_cm2=d.get("jsc_ma_cm2"),
                        ff=d.get("ff"),
                        pce_percent=d.get("pce_percent"),
                        vmp_v=d.get("vmp_v"),
                        jmp_ma_cm2=d.get("jmp_ma_cm2"),
                        pmp_mw_cm2=d.get("pmp_mw_cm2"),
                        warnings=d.get("warnings", [])
                    ))
    except Exception as e:
        print(f"WARNING: Failed to parse J-V metrics '{path}': {e}", file=sys.stderr)
    return metrics

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Recalculate EQE-derived Jsc from raw spectrum files.")
    parser.add_argument("eqe_folder", help="Directory containing raw EQE spectrum files.")
    parser.add_argument("--reference", help="Optional path to reference AM1.5G spectrum file.")
    parser.add_argument("--reported", help="Optional reported metrics CSV file to reconcile.")
    parser.add_argument("--jv-metrics", help="Optional path to compiled J-V metrics jsonl.")
    parser.add_argument("-o", "--output-dir", default="outputs/raw_pv", help="Directory for output files.")
    return parser.parse_args(args)

def run_eqe_recalculate(eqe_folder: str, reference_file: str | None = None, reported_file: str | None = None, jv_metrics_file: str | None = None, output_dir: str = "outputs/raw_pv") -> list[RawPVConsistencyFinding]:
    eqe_path = Path(eqe_folder)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    spectra_file = out_path / "eqe_spectra.jsonl"
    integration_file = out_path / "eqe_integration_results.jsonl"
    reconciliation_file = out_path / "eqe_reconciliation_findings.jsonl"
    summary_file = out_path / "eqe_recalculation_summary.md"

    # Load reference spectrum
    ref_spectrum, ref_warnings = load_reference_spectrum(reference_file)
    ref_name = Path(reference_file).name if reference_file else "embedded toy AM1.5G"

    # Find raw EQE files
    eqe_files = []
    if eqe_path.exists():
        if eqe_path.is_file():
            eqe_files = [eqe_path]
        else:
            for root, _, files in os.walk(eqe_path):
                for f in files:
                    if Path(f).suffix.lower() in (".csv", ".tsv", ".txt"):
                        eqe_files.append(Path(root) / f)

    # Read spectra and integrate Jsc
    spectra = []
    integration_results = []
    narrow_range_warnings = 0

    for eqe_f in eqe_files:
        spectrum = read_eqe_spectrum_file(str(eqe_f))
        spectra.append(spectrum)
        
        result = integrate_eqe_jsc(spectrum, ref_spectrum)
        integration_results.append(result)
        
        if "measured range narrower than reference range" in result.warnings:
            narrow_range_warnings += 1

    # Reconciliation
    reconciliation_findings = []
    reported_rows = []
    if reported_file:
        reported_rows = load_reported_metrics_csv(reported_file)
        reconciliation_findings.extend(reconcile_eqe_with_reported(integration_results, reported_rows))

    if jv_metrics_file:
        jv_metrics_list = load_jv_metrics_jsonl(jv_metrics_file)
        reconciliation_findings.extend(reconcile_eqe_with_jv(integration_results, jv_metrics_list))

    # Write files
    with spectra_file.open("w", encoding="utf-8") as f:
        for s in spectra:
            f.write(json.dumps(s.to_dict()) + "\n")

    with integration_file.open("w", encoding="utf-8") as f:
        for r in integration_results:
            f.write(json.dumps(r.to_dict()) + "\n")

    with reconciliation_file.open("w", encoding="utf-8") as f:
        for r in reconciliation_findings:
            f.write(json.dumps(r.to_dict()) + "\n")

    # Generate summary MD
    summary_lines = [
        "# EQE Recalculation Summary",
        "",
        f"- **Reference Spectrum Used**: `{ref_name}`",
        f"- **Number of spectra parsed**: {len(spectra)}",
        f"- **Wavelength range warnings**: {narrow_range_warnings}",
        f"- **Total integrated Jsc results**: {len(integration_results)}",
        f"- **Reported/EQE/JV reconciliation signals**: {len(reconciliation_findings)}",
        "",
        "## Integrated Jsc Results",
    ]
    
    for r in integration_results:
        summary_lines.append(f"  - Device `{r.device_id}`: {r.integrated_jsc_ma_cm2:.2f} mA/cm² (Spectrum: `{r.spectrum_id}`)")
        
    summary_lines.extend([
        "",
        "## Manual Verification Checklist",
        "- Retrieve raw monochromatic EQE/IPCE spectral data files.",
        "- Verify reference photodiode calibration trace.",
        "- Review device active/aperture mask geometry.",
        "- Confirm integration limits and reference ASTM spectrum.",
        "",
        "## Limitations",
        "- This recalculation does not perform spectral mismatch correction or reflectance correction.",
        "- Extrapolations beyond the measured EQE wavelength range are ignored (assumed zero).",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate consistency and integration signals for human review. It does not determine data fabrication or research misconduct."
    ])

    summary_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Wrote EQE spectra: {display_path(spectra_file)}")
    print(f"Wrote EQE integration results: {display_path(integration_file)}")
    print(f"Wrote EQE reconciliation findings: {display_path(reconciliation_file)}")
    print(f"Wrote EQE recalculation summary: {display_path(summary_file)}")

    return reconciliation_findings

def main(args=None):
    parsed = parse_args(args)
    run_eqe_recalculate(parsed.eqe_folder, parsed.reference, parsed.reported, parsed.jv_metrics, parsed.output_dir)

if __name__ == "__main__":
    main()
