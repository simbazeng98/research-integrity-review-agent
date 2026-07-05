from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding

def run_pv_stability_reporting_check(rows: list[PVMetricRow]) -> list[PVConsistencyFinding]:
    findings: list[PVConsistencyFinding] = []
    
    # Group rows by table_id
    tables_rows: dict[str, list[PVMetricRow]] = {}
    for row in rows:
        tables_rows.setdefault(row.table_id, []).append(row)

    finding_idx = 1

    for table_id, t_rows in tables_rows.items():
        source_file = t_rows[0].source_file
        raw_cols = list(t_rows[0].raw_values.keys())
        raw_cols_lower = [c.lower() for c in raw_cols]

        # Trigger conditions check
        has_stability_metrics = False
        
        # 1. Check if stability fields are non-empty in PVMetricRow
        for r in t_rows:
            if any(getattr(r, f, None) is not None for f in [
                "t80_h", "stabilized_pce_percent", "stabilized_power_output_percent",
                "mpp_tracking", "isos_protocol", "stability_duration_h"
            ]):
                has_stability_metrics = True
                break
                
        # 2. Check if table column names contain stability keywords
        stability_keywords = (
            "stability", "t80", "duration", "mpp", "isos", "degradation", 
            "retention", "aging", "damp heat", "light soaking", "thermal"
        )
        if any(any(kw in col for kw in stability_keywords) for col in raw_cols_lower):
            has_stability_metrics = True

        if not has_stability_metrics:
            continue

        missing_conditions = []

        # Check for duration
        has_duration = any(getattr(r, "t80_h", None) is not None or 
                           getattr(r, "stability_duration_h", None) is not None for r in t_rows) or \
                       any(any(k in col for k in ("duration", "time", "hours", "t80")) for col in raw_cols_lower)
        if not has_duration:
            missing_conditions.append("stress-test duration / aging time")

        # Check for temperature
        has_temp = any(getattr(r, "temperature_c", None) is not None for r in t_rows) or \
                   any(any(k in col for k in ("temp", "temperature")) for col in raw_cols_lower)
        if not has_temp:
            missing_conditions.append("temperature conditions")

        # Check for humidity/atmosphere
        has_humidity = any(getattr(r, "humidity_percent", None) is not None for r in t_rows) or \
                       any(any(k in col for k in ("humidity", "rh", "atmosphere", "nitrogen", "n2", "air", "ambient")) for col in raw_cols_lower)
        if not has_humidity:
            missing_conditions.append("humidity or atmospheric environment")

        # Check for illumination
        has_illumination = any(any(k in col for k in ("light", "illumination", "soaking", "led", "suns", "am1.5", "dark")) for col in raw_cols_lower)
        if not has_illumination:
            missing_conditions.append("illumination conditions (light soaking / dark)")

        # Check for bias / electrical load condition
        has_bias = any(getattr(r, "mpp_tracking", None) is not None for r in t_rows) or \
                   any(any(k in col for k in ("bias", "mpp", "load", "open circuit", "short circuit", "voc", "jsc", "electrical")) for col in raw_cols_lower)
        if not has_bias:
            missing_conditions.append("electrical bias condition (MPP tracking, open circuit, short circuit)")

        # Check for encapsulation
        has_encap = any(getattr(r, "encapsulation", None) is not None for r in t_rows) or \
                    any(any(k in col for k in ("encapsulation", "encap", "epoxy", "glass", "capsulation")) for col in raw_cols_lower)
        if not has_encap:
            missing_conditions.append("encapsulation status")

        # Check for initial/final PCE or retention
        has_retention = any(getattr(r, "stabilized_pce_percent", None) is not None or 
                            getattr(r, "stabilized_power_output_percent", None) is not None for r in t_rows) or \
                        any(any(k in col for k in ("retention", "degradation", "ret", "pce", "efficiency", "drop", "decay", "initial", "final")) for col in raw_cols_lower)
        if not has_retention:
            missing_conditions.append("initial and final PCE or retention values")

        if missing_conditions:
            observed = {
                "missing_conditions": missing_conditions,
                "present_stability_fields": [col for col in raw_cols if any(kw in col.lower() for kw in stability_keywords)]
            }

            safe_lang = (
                f"PV stability reporting completeness signal: stability-related values are present, "
                f"but one or more stress-test conditions ({', '.join(missing_conditions)}) appear missing from the parsed tables. "
                f"Verify the manuscript methods, SI, and raw ageing logs."
            )

            evidence_items = [{
                "location": f"Table {table_id}",
                "message": f"Table '{source_file}' lists stability test outcomes but omits critical aging parameters: {', '.join(missing_conditions)}."
            }]

            finding = PVConsistencyFinding(
                finding_id=f"PV-STAB-FIND-{finding_idx:03d}",
                rule_id="pv_stability_reporting_completeness",
                detector_id="stability_reporting",
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
                    "Aging protocols and environment descriptions are documented in the main text or SI methods rather than the summary table",
                    "The stability test is qualitative or standard and relies on general lab defaults",
                    "Table headers use non-standard acronyms for stress conditions"
                ],
                false_positive_risks=[
                    "The table summarizes outcomes from standard ISOS protocols described fully in the literature references",
                    "Data represents early screening tests rather than standardized stability runs"
                ],
                manual_verification=[
                    "Verify the aging setup parameters (temperature, RH, electrical load, light spectrum) in the methods section",
                    "Check for supplementary data sheets containing raw time-series degradation logs",
                    "Confirm if the aging experiment aligns with standard ISOS protocols (e.g. ISOS-D-1, ISOS-L-1)"
                ],
                limitations=[
                    "Cannot parse conditions described in unstructured text or figure captions"
                ],
                metadata={
                    "missing_conditions": missing_conditions,
                    "table_columns": raw_cols
                }
            )
            findings.append(finding)
            finding_idx += 1

    return findings
