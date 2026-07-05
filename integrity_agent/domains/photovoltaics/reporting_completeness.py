from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding

def run_pv_reporting_completeness_check(
    rows: list[PVMetricRow],
    field_mappings: list[dict] | None = None,
    table_context: dict | None = None
) -> list[PVConsistencyFinding]:
    findings: list[PVConsistencyFinding] = []
    
    # Group rows by table_id
    tables_rows: dict[str, list[PVMetricRow]] = {}
    for row in rows:
        tables_rows.setdefault(row.table_id, []).append(row)

    finding_idx = 1

    for table_id, t_rows in tables_rows.items():
        # Check if this table has any mapped PV fields
        has_pv_fields = False
        source_file = t_rows[0].source_file
        
        # We can look at all columns present in the raw_values
        raw_cols = list(t_rows[0].raw_values.keys())
        raw_cols_lower = [c.lower() for c in raw_cols]

        for r in t_rows:
            if any(val is not None for val in [
                r.voc_v, r.jsc_ma_cm2, r.ff, r.pce_percent, 
                r.eqe_jsc_ma_cm2, r.bandgap_ev, r.active_area_cm2, r.aperture_area_cm2
            ]):
                has_pv_fields = True
                break

        if not has_pv_fields:
            continue

        missing_fields = []

        # Check for device area
        if all(getattr(r, "active_area_cm2", None) is None and 
               getattr(r, "aperture_area_cm2", None) is None and 
               getattr(r, "mask_area_cm2", None) is None for r in t_rows):
            missing_fields.append("device area (active/aperture/mask area)")

        # Check for scan direction
        if all(getattr(r, "scan_direction", None) is None for r in t_rows):
            missing_fields.append("scan direction (forward/reverse)")

        # Check for scan rate
        if all(getattr(r, "scan_rate", None) is None for r in t_rows):
            missing_fields.append("scan rate (mV/s or V/s)")

        # Check for environment
        if all(getattr(r, "temperature_c", None) is None and 
               getattr(r, "humidity_percent", None) is None for r in t_rows):
            missing_fields.append("test environment (temperature/humidity)")

        # Check for EQE-integrated Jsc
        if all(getattr(r, "eqe_jsc_ma_cm2", None) is None for r in t_rows):
            missing_fields.append("EQE-integrated Jsc comparison")

        # Check for stability metrics (only check if table headers hint at stability)
        has_stability_hint = any(any(k in col for k in ("stabil", "t80", "degrad", "retent", "isos", "aging")) for col in raw_cols_lower)
        if has_stability_hint:
            if all(getattr(r, "t80_h", None) is None and 
                   getattr(r, "stabilized_pce_percent", None) is None for r in t_rows):
                missing_fields.append("stability reporting details (T80, duration, stabilized PCE)")

        # Check for statistics/number of cells
        has_stats = any(any(k in col for k in ("std", "dev", "mean", "avg", "average", "error", "champion", "best", "number", "count")) for col in raw_cols_lower)
        if not has_stats:
            missing_fields.append("cell statistics (number of cells tested, mean, standard deviation)")

        # Check for calibration / simulator details
        has_calib = any(any(k in col for k in ("calib", "ref cell", "simulator", "spectral mismatch")) for col in raw_cols_lower)
        if not has_calib:
            missing_fields.append("light source calibration reference")

        # Check for tandem-specific details if tandem context detected
        is_tandem = any(any(k in col for k in ("tandem", "2t", "4t", "subcell", "top cell", "bottom cell", "filter")) for col in raw_cols_lower)
        if is_tandem:
            has_tandem_bias = any(any(k in col for k in ("bias", "filtered")) for col in raw_cols_lower)
            if not has_tandem_bias:
                missing_fields.append("tandem subcell bias illumination or bias voltage")

        if missing_fields:
            observed = {
                "missing_fields": missing_fields,
                "parsed_fields": [k for k, v in t_rows[0].to_dict().items() if v is not None and k not in ("row_id", "source_file", "table_id", "row_index", "raw_values", "warnings")]
            }

            safe_lang = (
                f"PV reporting completeness gap detected: the following recommended characterization metadata fields appear missing "
                f"from the parsed table: {', '.join(missing_fields)}. This does not imply data fabrication; "
                f"it identifies missing or unparsed information that may be needed to reproduce or compare device characterization."
            )

            evidence_items = [{
                "location": f"Table {table_id}",
                "message": f"Table '{source_file}' has mapped PV parameters but is missing reporting checklist items: {', '.join(missing_fields)}."
            }]

            finding = PVConsistencyFinding(
                finding_id=f"PV-REPORT-FIND-{finding_idx:03d}",
                rule_id="pv_reporting_completeness",
                detector_id="reporting_completeness",
                risk_level="low",
                risk_ceiling="low",
                source_file=source_file,
                table_id=table_id,
                row_index=None,
                device_id=None,
                observed_values=observed,
                recomputed_values={},
                tolerance=None,
                evidence_items=evidence_items,
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "Information may be reported in the manuscript text, methods section, or supplementary information rather than the source table",
                    "The parsed table represents a simple summary rather than a full characterization log",
                    "Metadata columns were not parsed due to non-standard naming conventions"
                ],
                false_positive_risks=[
                    "The experiment did not require certain measurements (e.g. no stability testing performed)",
                    "Data is from a legacy dataset where certain parameters were not recorded"
                ],
                manual_verification=[
                    "Check the main text and supplementary materials of the manuscript for the missing details",
                    "Verify the original instrument files and measurement logs"
                ],
                limitations=[
                    "Cannot verify information outside of the provided source tables"
                ],
                metadata={
                    "missing_fields": missing_fields,
                    "is_tandem": is_tandem,
                    "has_stability_hint": has_stability_hint
                }
            )
            findings.append(finding)
            finding_idx += 1

    return findings
