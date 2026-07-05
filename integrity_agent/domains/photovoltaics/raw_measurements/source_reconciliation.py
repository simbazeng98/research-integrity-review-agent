from __future__ import annotations

import math
from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.raw_measurements.schema import (
    JVMetrics, EQEIntegrationResult, RawPVConsistencyFinding
)

def reconcile_jv_metrics_with_reported(jv_metrics: list[JVMetrics], reported_rows: list[PVMetricRow]) -> list[RawPVConsistencyFinding]:
    findings = []
    finding_counter = 1
    
    # Map reported rows by device_id (clean lowercase)
    reported_map: dict[str, list[PVMetricRow]] = {}
    for r in reported_rows:
        if r.device_id:
            dev_clean = r.device_id.strip().lower()
            reported_map.setdefault(dev_clean, []).append(r)

    for jv in jv_metrics:
        dev_id = jv.device_id
        if not dev_id or dev_id == "unknown":
            continue
            
        dev_clean = dev_id.strip().lower()
        matched_rows = reported_map.get(dev_clean, [])
        if not matched_rows:
            continue
            
        for r_row in matched_rows:
            mismatches = []
            obs_vals = {}
            recomp_vals = {}
            
            # Voc check (tolerance abs 0.02 V)
            if jv.voc_v is not None and r_row.voc_v is not None:
                diff_voc = abs(jv.voc_v - r_row.voc_v)
                obs_vals["reported_voc_v"] = r_row.voc_v
                recomp_vals["recalculated_voc_v"] = jv.voc_v
                if diff_voc > 0.02:
                    mismatches.append(f"Voc (reported: {r_row.voc_v}V, recalculated: {jv.voc_v:.3f}V, diff: {diff_voc:.3f}V)")
            
            # Jsc check (tolerance abs 0.5 mA/cm2 or rel 3%)
            if jv.jsc_ma_cm2 is not None and r_row.jsc_ma_cm2 is not None:
                diff_jsc = abs(jv.jsc_ma_cm2 - r_row.jsc_ma_cm2)
                rel_jsc = diff_jsc / r_row.jsc_ma_cm2 if r_row.jsc_ma_cm2 != 0 else 0
                obs_vals["reported_jsc_ma_cm2"] = r_row.jsc_ma_cm2
                recomp_vals["recalculated_jsc_ma_cm2"] = jv.jsc_ma_cm2
                if diff_jsc > 0.5 and rel_jsc > 0.03:
                    mismatches.append(f"Jsc (reported: {r_row.jsc_ma_cm2} mA/cm², recalculated: {jv.jsc_ma_cm2:.2f} mA/cm²)")
            
            # FF check (tolerance abs 0.03)
            if jv.ff is not None and r_row.ff is not None:
                diff_ff = abs(jv.ff - r_row.ff)
                obs_vals["reported_ff"] = r_row.ff
                recomp_vals["recalculated_ff"] = jv.ff
                if diff_ff > 0.03:
                    mismatches.append(f"FF (reported: {r_row.ff}, recalculated: {jv.ff:.3f})")
            
            # PCE check (tolerance abs 0.5% or rel 5%)
            if jv.pce_percent is not None and r_row.pce_percent is not None:
                diff_pce = abs(jv.pce_percent - r_row.pce_percent)
                rel_pce = diff_pce / r_row.pce_percent if r_row.pce_percent != 0 else 0
                obs_vals["reported_pce_percent"] = r_row.pce_percent
                recomp_vals["recalculated_pce_percent"] = jv.pce_percent
                if diff_pce > 0.5 and rel_pce > 0.05:
                    mismatches.append(f"PCE (reported: {r_row.pce_percent}%, recalculated: {jv.pce_percent:.2f}%)")

            if mismatches:
                safe_lang = (
                    f"Candidate raw/source-data reconciliation signal: recalculated raw J–V sweep metrics "
                    f"for device '{dev_id}' differ from reported table metrics (Differences: {'; '.join(mismatches)}). "
                    f"Verify device mapping, units, sign convention, formulas, measurement protocol, "
                    f"and whether reported values are scan-derived or stabilized."
                )
                findings.append(RawPVConsistencyFinding(
                    finding_id=f"RAW-PV-FIND-JV-REC-{finding_counter:03d}",
                    rule_id="pv_source_reconciliation",
                    detector_id="source_reconciliation",
                    risk_level="medium",
                    risk_ceiling="medium",
                    source_file=r_row.source_file,
                    device_id=dev_id,
                    observed_values=obs_vals,
                    recomputed_values=recomp_vals,
                    tolerance={
                        "voc_v_abs": 0.02,
                        "jsc_ma_cm2_abs": 0.5,
                        "jsc_ma_cm2_rel": 0.03,
                        "ff_abs": 0.03,
                        "pce_percent_abs": 0.5,
                        "pce_percent_rel": 0.05
                    },
                    evidence_items=[{
                        "location": f"Device {dev_id} vs Table Row {r_row.row_index}",
                        "message": f"Mismatches: {'; '.join(mismatches)}"
                    }],
                    safe_report_language=safe_lang,
                    alternative_explanations=[
                        "wrong device mapping",
                        "rounding",
                        "unit convention",
                        "scan direction mismatch",
                        "stabilized vs scan-derived metric",
                        "area basis mismatch",
                        "light intensity mismatch",
                        "instrument export sign convention",
                        "parser limitation"
                    ],
                    false_positive_risks=[
                        "Standard rounding differences in manual summary tables",
                        "PCE derived from stabilized maximum power point output rather than dynamic J-V scan"
                    ],
                    manual_verification=[
                        "raw J–V files",
                        "reported metric table",
                        "spreadsheet formulas",
                        "device ID mapping",
                        "measurement protocol"
                    ],
                    limitations=[
                        "Reconciliation depends on exact device ID matching which can fail on custom naming conventions"
                    ],
                    metadata={
                        "curve_id": jv.curve_id,
                        "table_id": r_row.table_id,
                        "row_id": r_row.row_id
                    }
                ))
                finding_counter += 1

    return findings

def reconcile_eqe_with_reported(eqe_results: list[EQEIntegrationResult], reported_rows: list[PVMetricRow]) -> list[RawPVConsistencyFinding]:
    findings = []
    finding_counter = 1
    
    reported_map: dict[str, list[PVMetricRow]] = {}
    for r in reported_rows:
        if r.device_id:
            dev_clean = r.device_id.strip().lower()
            reported_map.setdefault(dev_clean, []).append(r)

    for eqe in eqe_results:
        dev_id = eqe.device_id
        if not dev_id or dev_id == "unknown":
            continue
            
        dev_clean = dev_id.strip().lower()
        matched_rows = reported_map.get(dev_clean, [])
        if not matched_rows:
            continue
            
        for r_row in matched_rows:
            # Compare EQE Jsc (tolerance abs 1.0 mA/cm2 or rel 10%)
            if eqe.integrated_jsc_ma_cm2 is not None and r_row.eqe_jsc_ma_cm2 is not None:
                obs_jsc = r_row.eqe_jsc_ma_cm2
                recomp_jsc = eqe.integrated_jsc_ma_cm2
                diff_jsc = abs(recomp_jsc - obs_jsc)
                rel_jsc = diff_jsc / obs_jsc if obs_jsc != 0 else 0
                
                if diff_jsc > 1.0 and rel_jsc > 0.10:
                    safe_lang = (
                        f"Candidate raw/source-data reconciliation signal: recalculated integrated EQE Jsc "
                        f"({recomp_jsc:.2f} mA/cm²) differs from reported EQE Jsc ({obs_jsc:.2f} mA/cm²) beyond "
                        f"tolerance for device '{dev_id}'. Verify device mapping, units, reference spectrum, and integration limits."
                    )
                    findings.append(RawPVConsistencyFinding(
                        finding_id=f"RAW-PV-FIND-EQE-REC-{finding_counter:03d}",
                        rule_id="pv_source_reconciliation",
                        detector_id="source_reconciliation",
                        risk_level="medium",
                        risk_ceiling="medium",
                        source_file=r_row.source_file,
                        device_id=dev_id,
                        observed_values={"reported_eqe_jsc_ma_cm2": obs_jsc},
                        recomputed_values={"recalculated_eqe_jsc_ma_cm2": recomp_jsc},
                        tolerance={
                            "jsc_ma_cm2_abs": 1.0,
                            "jsc_ma_cm2_rel": 0.10
                        },
                        evidence_items=[{
                            "location": f"Device {dev_id} vs Table Row {r_row.row_index}",
                            "message": f"Reported EQE Jsc: {obs_jsc} mA/cm², Recalculated: {recomp_jsc:.2f} mA/cm²"
                        }],
                        safe_report_language=safe_lang,
                        alternative_explanations=[
                            "wrong device mapping",
                            "different integration limits or solar spectrum",
                            "rounding differences",
                            "spectral mismatch factor correction differences",
                            "instrument export sign convention",
                            "parser limitation"
                        ],
                        false_positive_risks=[
                            "Standard small variations from integration limits or choice of ASTM AM1.5G spectrum",
                            "Minor rounding or manual transcription differences"
                        ],
                        manual_verification=[
                            "raw EQE spectra",
                            "reported metric table",
                            "device ID mapping",
                            "analysis script"
                        ],
                        limitations=[
                            "Reconciliation is limited to matching based on parsed device ID names"
                        ],
                        metadata={
                            "spectrum_id": eqe.spectrum_id,
                            "table_id": r_row.table_id,
                            "row_id": r_row.row_id
                        }
                    ))
                    finding_counter += 1

    return findings

def reconcile_eqe_with_jv(eqe_results: list[EQEIntegrationResult], jv_metrics: list[JVMetrics]) -> list[RawPVConsistencyFinding]:
    findings = []
    finding_counter = 1
    
    jv_map = {jv.device_id.strip().lower(): jv for jv in jv_metrics if jv.device_id and jv.device_id != "unknown"}

    for eqe in eqe_results:
        dev_id = eqe.device_id
        if not dev_id or dev_id == "unknown":
            continue
            
        dev_clean = dev_id.strip().lower()
        jv = jv_map.get(dev_clean)
        if not jv or jv.jsc_ma_cm2 is None:
            continue
            
        # Compare integrated EQE Jsc vs J-V Jsc
        jv_jsc = jv.jsc_ma_cm2
        eqe_jsc = eqe.integrated_jsc_ma_cm2
        
        diff_jsc = abs(jv_jsc - eqe_jsc)
        rel_jsc = diff_jsc / jv_jsc if jv_jsc != 0 else 0
        
        # 4-5% mismatch is typical, >10% with abs >1.0 mA/cm2 is flagged
        if rel_jsc > 0.10 and diff_jsc > 1.0:
            safe_lang = (
                f"Candidate raw EQE vs J–V current density mismatch: recomputed integrated EQE Jsc "
                f"({eqe_jsc:.2f} mA/cm²) differs from recomputed J–V Jsc ({jv_jsc:.2f} mA/cm²) by {rel_jsc*100:.1f}% "
                f"for device '{dev_id}'. Verify spectral mismatch correction, simulator calibration, and measurement delays."
            )
            findings.append(RawPVConsistencyFinding(
                finding_id=f"RAW-PV-FIND-EQE-JV-MIS-{finding_counter:03d}",
                rule_id="pv_eqe_spectrum_integration",
                detector_id="eqe_jv_reconciliation",
                risk_level="medium",
                risk_ceiling="medium",
                source_file=jv.curve_id,
                device_id=dev_id,
                observed_values={"recalculated_jv_jsc_ma_cm2": jv_jsc},
                recomputed_values={"recalculated_eqe_jsc_ma_cm2": eqe_jsc},
                tolerance={
                    "rel_threshold": 0.10,
                    "abs_threshold": 1.0
                },
                evidence_items=[{
                    "location": f"Device {dev_id}",
                    "message": f"Recalculated JV Jsc: {jv_jsc:.2f} mA/cm², Recalculated EQE Jsc: {eqe_jsc:.2f} mA/cm², Rel Diff: {rel_jsc*100:.1f}%"
                }],
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "spectral mismatch factor correction not applied or calculated with different reference spectrum",
                    "discrepancy in the active area vs aperture area used for cell and EQE measurements",
                    "solar simulator drift or calibration error on the date of J-V measurement",
                    "optical reflective/transmission losses not accounted for in EQE setup",
                    "device degradation or hysteresis effects between EQE and J-V measurements",
                    "measurements conducted on different dates under varying ambient temperature/humidity",
                    "legitimate systematic discrepancy due to carrier collection efficiency differences under monochromatic vs white light bias"
                ],
                false_positive_risks=[
                    "Typical physical variations (up to 5-10%) between different measurement setups",
                    "Instrument calibration differences on the day of testing"
                ],
                manual_verification=[
                    "raw EQE spectra and raw J-V sweep files",
                    "review solar simulator calibration and spectral mismatch correction logs",
                    "verify cell area aperture/mask dimensions under a microscope",
                    "verify exact dates and environmental conditions of both measurements"
                ],
                limitations=[
                    "Does not recalculate current from raw EQE spectrum file itself in v0.10/v0.11 if spectral shape is corrupted"
                ],
                metadata={
                    "spectrum_id": eqe.spectrum_id,
                    "curve_id": jv.curve_id
                }
            ))
            finding_counter += 1

    return findings
