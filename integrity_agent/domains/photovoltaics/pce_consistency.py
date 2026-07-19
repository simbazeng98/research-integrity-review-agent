from __future__ import annotations

import re

from integrity_agent.domains.photovoltaics.field_mapping import light_intensity_exact
from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding


def _reported_illumination_columns(row: PVMetricRow) -> list[str]:
    columns = []
    for column_name in row.raw_values:
        column_clean = str(column_name).strip().lower()
        if any(re.search(pattern, column_clean) for pattern in light_intensity_exact):
            columns.append(str(column_name))
    return columns

def run_pce_consistency_check(
    rows: list[PVMetricRow],
    tolerance_abs: float = 0.3,
    tolerance_rel: float = 0.03
) -> list[PVConsistencyFinding]:
    findings: list[PVConsistencyFinding] = []
    finding_idx = 1

    for row in rows:
        # Check if all required fields are present
        if (row.voc_v is None or row.jsc_ma_cm2 is None or 
            row.ff is None or row.pce_percent is None):
            continue

        # Do not silently substitute one-sun conditions when the source table
        # explicitly reports an illumination field that could not be parsed.
        illumination_columns = _reported_illumination_columns(row)
        has_illumination_parse_warning = any(
            "light intensity" in warning.lower() for warning in row.warnings
        )
        invalid_reported_illumination = (
            row.light_intensity_mw_cm2 is not None
            and row.light_intensity_mw_cm2 <= 0
        )
        if (
            row.light_intensity_mw_cm2 is None
            and (illumination_columns or has_illumination_parse_warning)
        ) or invalid_reported_illumination:
            finding = PVConsistencyFinding(
                finding_id=f"PV-PCE-FIND-{finding_idx:03d}",
                rule_id="pv_pce_missing_illumination_context",
                detector_id="pce_consistency",
                risk_level="low",
                risk_ceiling="low",
                source_file=row.source_file,
                table_id=row.table_id,
                row_index=row.row_index,
                device_id=row.device_id,
                observed_values={
                    "light_intensity_mw_cm2": row.light_intensity_mw_cm2,
                    "reported_illumination_columns": illumination_columns,
                    "parse_warnings": [
                        warning for warning in row.warnings
                        if "light intensity" in warning.lower()
                    ],
                },
                recomputed_values={},
                evidence_items=[{
                    "location": f"Row {row.row_index}",
                    "message": (
                        "An illumination-intensity field was reported but could not be parsed "
                        "as a positive numeric value; PCE was not recomputed using a one-sun default."
                    ),
                }],
                safe_report_language=(
                    "PV measurement-context completeness signal: the reported illumination "
                    "intensity could not be parsed as a positive numeric value. Verify the "
                    "measurement basis before recomputing PCE."
                ),
                alternative_explanations=[
                    "The illumination value may be encoded as text or use an unsupported unit.",
                    "The numeric calibration value may be documented outside the parsed table.",
                ],
                false_positive_risks=[
                    "The table may use a non-standard label or formatting for a valid calibration value."
                ],
                manual_verification=[
                    "Verify the light-source calibration value and units in the methods or raw measurement log."
                ],
                limitations=[
                    "PCE consistency cannot be evaluated without a usable illumination intensity."
                ],
                metadata={"illumination_context_present": True},
            )
            findings.append(finding)
            finding_idx += 1
            continue

        # Determine light intensity. Preserve the historical one-sun default
        # only when the input contains no reported illumination context.
        light_intensity = 100.0
        is_non_standard_light = False
        if row.light_intensity_mw_cm2 is not None and row.light_intensity_mw_cm2 > 0:
            light_intensity = row.light_intensity_mw_cm2
            if abs(light_intensity - 100.0) > 1e-3:
                is_non_standard_light = True

        # Recompute PCE: Voc(V) * Jsc(mA/cm2) * FF(fraction) / Pin(mW/cm2) * 100%
        # If FF is reported as fraction (0.55), Voc * Jsc * FF is in mW/cm2.
        # PCE (%) = (Voc * Jsc * FF / light_intensity) * 100.0
        recomputed_pce = (row.voc_v * row.jsc_ma_cm2 * row.ff / light_intensity) * 100.0
        
        abs_diff = abs(row.pce_percent - recomputed_pce)
        rel_diff = abs_diff / max(abs(row.pce_percent), 1e-6)

        if abs_diff > tolerance_abs or rel_diff > tolerance_rel:
            observed = {
                "voc_v": row.voc_v,
                "jsc_ma_cm2": row.jsc_ma_cm2,
                "ff": row.ff,
                "ff_unit": row.ff_unit,
                "pce_percent": row.pce_percent,
                "light_intensity_mw_cm2": row.light_intensity_mw_cm2
            }
            recomputed = {
                "pce_percent": recomputed_pce
            }

            intensity_msg = "under the assumed 100 mW/cm² illumination basis"
            if row.light_intensity_mw_cm2 is not None:
                intensity_msg = f"under the specified {light_intensity} mW/cm² illumination basis"

            safe_lang = (
                f"Candidate PV metric consistency signal: reported PCE ({row.pce_percent}%) differs from "
                f"recomputed Voc × Jsc × FF ({recomputed_pce:.2f}%) {intensity_msg}. "
                f"Verify units, FF convention, area basis, rounding, and whether the value is stabilized or scan-specific."
            )

            evidence_items = [{
                "location": f"Row {row.row_index}",
                "message": (
                    f"Reported PCE: {row.pce_percent}%, Recomputed: {recomputed_pce:.4f}% "
                    f"(Voc={row.voc_v}V, Jsc={row.jsc_ma_cm2}mA/cm2, FF={row.ff:.4f}, Pin={light_intensity}mW/cm2)"
                )
            }]

            finding = PVConsistencyFinding(
                finding_id=f"PV-PCE-FIND-{finding_idx:03d}",
                rule_id="pv_pce_consistency",
                detector_id="pce_consistency",
                risk_level="medium",
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
                    "FF reported as percent vs fraction in raw spreadsheet calculations",
                    "PCE derived from stabilized power output rather than scan-derived J-V curves",
                    "PCE and J-V metrics extracted from different scan directions (forward vs reverse)",
                    "Severe rounding errors in reported values",
                    "Differences in device area definitions used for Jsc vs PCE calculations",
                    "Non-1-sun illumination intensity used in measurement but not adjusted in formula",
                    "Typographical errors during table manual transcription",
                    "Unit conversion mismatch during data aggregation"
                ],
                false_positive_risks=[
                    "Rounding differences when values are printed to few significant digits",
                    "Stabilized power conversion efficiency reported alongside initial scan-based Voc/Jsc/FF",
                    "Misidentified column mapping for fill factor or current density",
                    "Correctly reported parameters for non-standard testing conditions"
                ],
                manual_verification=[
                    "Retrieve raw J-V curves and re-evaluate parameters",
                    "Check spreadsheet formulas for conversion factors or hidden calculations",
                    "Verify the active and aperture area definitions",
                    "Confirm the light simulator intensity calibration logs",
                    "Verify whether PCE corresponds to champion device J-V scan or stabilized MPP tracking"
                ],
                limitations=[
                    "This test relies on the correctness of field mappings",
                    "Assumes standard solar simulator illumination unless light intensity is explicitly column-profiled"
                ],
                metadata={
                    "abs_diff": abs_diff,
                    "rel_diff": rel_diff,
                    "is_non_standard_light": is_non_standard_light
                }
            )
            findings.append(finding)
            finding_idx += 1

    return findings
