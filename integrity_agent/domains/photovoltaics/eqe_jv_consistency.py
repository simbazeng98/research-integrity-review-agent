from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding

def run_eqe_jv_jsc_consistency_check(
    rows: list[PVMetricRow],
    tolerance_rel: float = 0.10,
    tolerance_abs: float = 1.0
) -> list[PVConsistencyFinding]:
    findings: list[PVConsistencyFinding] = []
    finding_idx = 1

    for row in rows:
        if row.jsc_ma_cm2 is None or row.eqe_jsc_ma_cm2 is None:
            continue

        jv_jsc = row.jsc_ma_cm2
        eqe_jsc = row.eqe_jsc_ma_cm2

        # Avoid division by zero
        if abs(jv_jsc) < 1e-6:
            continue

        abs_diff = abs(jv_jsc - eqe_jsc)
        rel_diff = abs_diff / abs(jv_jsc)

        # Decide risk level based on thresholds
        # Medium if abs_diff > tolerance_abs and rel_diff > tolerance_rel
        # Low if rel_diff > 0.05 (but not medium)
        # Skip if rel_diff <= 0.05 (typical discrepancy range)
        if abs_diff > tolerance_abs and rel_diff > tolerance_rel:
            risk = "medium"
        elif rel_diff > 0.05:
            risk = "low"
        else:
            continue

        observed = {
            "jv_jsc_ma_cm2": jv_jsc,
            "eqe_jsc_ma_cm2": eqe_jsc
        }
        recomputed = {
            "difference_abs": abs_diff,
            "difference_rel": rel_diff
        }

        safe_lang = (
            f"Candidate EQE/J–V current-density consistency signal: integrated EQE-derived Jsc ({eqe_jsc:.2f} mA/cm²) "
            f"differs from J–V Jsc ({jv_jsc:.2f} mA/cm²) beyond the configured threshold. "
            f"Verify spectral mismatch correction, light calibration, integration spectrum, device area, and scan/stabilization conditions."
        )

        evidence_items = [{
            "location": f"Row {row.row_index}",
            "message": (
                f"J-V Jsc: {jv_jsc} mA/cm2, EQE Jsc: {eqe_jsc} mA/cm2, "
                f"Abs Diff: {abs_diff:.4f} mA/cm2, Rel Diff: {rel_diff*100:.2f}%"
            )
        }]

        finding = PVConsistencyFinding(
            finding_id=f"PV-EQE-FIND-{finding_idx:03d}",
            rule_id="pv_eqe_jv_jsc_consistency",
            detector_id="eqe_jv_consistency",
            risk_level=risk,
            risk_ceiling="medium",
            source_file=row.source_file,
            table_id=row.table_id,
            row_index=row.row_index,
            device_id=row.device_id,
            observed_values=observed,
            recomputed_values=recomputed,
            tolerance={"abs": tolerance_abs, "rel": tolerance_rel},
            evidence_items=evidence_items,
            safe_report_language=safe_lang,
            alternative_explanations=[
                "Spectral mismatch factor correction not applied or calculated with different reference spectrum",
                "Discrepancy in the active area vs aperture area used for cell and EQE measurements",
                "Solar simulator drift or calibration error on the date of J-V measurement",
                "Different integration limits or reference solar spectrum (e.g. AM1.5G) used for EQE integration",
                "Optical reflective/transmission losses not accounted for in EQE setup",
                "Device degradation or hysteresis effects between EQE and J-V measurements",
                "Measurements conducted on different dates under varying ambient temperature/humidity",
                "Legitimate systematic discrepancy due to carrier collection efficiency differences under monochromatic vs white light bias"
            ],
            false_positive_risks=[
                "Normal physical variations (up to 5-10%) between different measurement setups",
                "Minor mismatch due to rounded values in the summary table",
                "Intentional non-standard testing for specific research questions"
            ],
            manual_verification=[
                "Inspect raw EQE spectral response curves and integration files",
                "Review the solar simulator calibration and spectral mismatch correction logs",
                "Verify cell area aperture/mask dimensions under a microscope or calibrated imaging system",
                "Compare J-V curves with EQE-derived currents across multiple devices",
                "Verify the exact dates and environmental conditions of both measurements"
            ],
            limitations=[
                "Requires both J-V current density and integrated EQE current density columns to be present and mapped",
                "Does not recalculate current from the raw EQE spectrum file itself in v0.10"
            ],
            metadata={
                "jv_jsc": jv_jsc,
                "eqe_jsc": eqe_jsc,
                "abs_diff": abs_diff,
                "rel_diff": rel_diff,
                "threshold_abs": tolerance_abs,
                "threshold_rel": tolerance_rel
            }
        )
        findings.append(finding)
        finding_idx += 1

    return findings
