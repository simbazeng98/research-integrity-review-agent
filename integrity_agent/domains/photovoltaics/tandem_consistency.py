from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding
from integrity_agent.domains.photovoltaics.units import to_float

def run_tandem_consistency_check(rows: list[PVMetricRow]) -> list[PVConsistencyFinding]:
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

        # Check for tandem context keywords
        tandem_keywords = (
            "tandem", "2t", "4t", "top cell", "bottom cell", "subcell", 
            "current matching", "filtered jsc", "iii-v", "si/perovskite", 
            "perovskite/si", "gaas", "ge", "ingaas"
        )
        has_tandem_context = any(any(kw in col for kw in tandem_keywords) for col in raw_cols_lower)
        if not has_tandem_context:
            continue

        for row in t_rows:
            top_jsc = None
            bottom_jsc = None
            top_pce = None
            bottom_pce = None
            total_pce = row.pce_percent
            is_2t = False
            is_4t = False

            # Search in raw_values
            for col_name, val_str in row.raw_values.items():
                if val_str is None or str(val_str).strip() == "":
                    continue
                val = to_float(val_str)
                col_lower = col_name.lower()
                
                val_str_lower = str(val_str).lower()
                if "2t" in col_lower or "2-terminal" in col_lower or "2t" in val_str_lower or "2-terminal" in val_str_lower:
                    is_2t = True
                elif "4t" in col_lower or "4-terminal" in col_lower or "4t" in val_str_lower or "4-terminal" in val_str_lower:
                    is_4t = True
                    is_2t = False
                    
                if "top" in col_lower or "front" in col_lower or "subcell1" in col_lower:
                    if "jsc" in col_lower or "current" in col_lower:
                        top_jsc = val
                    elif "pce" in col_lower or "eff" in col_lower or "eta" in col_lower or "η" in col_lower:
                        top_pce = val
                elif "bottom" in col_lower or "back" in col_lower or "rear" in col_lower or "subcell2" in col_lower:
                    if "jsc" in col_lower or "current" in col_lower:
                        bottom_jsc = val
                    elif "pce" in col_lower or "eff" in col_lower or "eta" in col_lower or "η" in col_lower:
                        bottom_pce = val
                elif "total" in col_lower or "tandem" in col_lower:
                    if "pce" in col_lower or "eff" in col_lower or "eta" in col_lower or "η" in col_lower:
                        total_pce = val

            # Heuristics for 2T vs 4T if not explicitly specified
            if not is_2t and not is_4t:
                if top_pce is not None and bottom_pce is not None and total_pce is not None:
                    # If total is close to sum, assume 4T
                    if abs(total_pce - (top_pce + bottom_pce)) < 1.0:
                        is_4t = True
                    else:
                        is_2t = True
                else:
                    is_2t = True # default assumption

            # Case 1: 4T tandem efficiency check
            if is_4t and top_pce is not None and bottom_pce is not None and total_pce is not None:
                expected_pce = top_pce + bottom_pce
                if total_pce > expected_pce + 0.3:
                    observed = {
                        "top_pce": top_pce,
                        "bottom_pce": bottom_pce,
                        "reported_total_pce": total_pce
                    }
                    recomputed = {
                        "expected_total_pce": expected_pce
                    }
                    
                    safe_lang = (
                        f"Candidate tandem PV consistency signal: 4T tandem reported total PCE ({total_pce}%) "
                        f"exceeds the sum of top and bottom subcells ({expected_pce}%). "
                        f"Verify subcell calibration, area basis, spectral mismatch correction, and filter geometry."
                    )
                    
                    evidence_items = [{
                        "location": f"Row {row.row_index}",
                        "message": f"4T Tandem: Top PCE={top_pce}%, Bottom PCE={bottom_pce}%, Sum={expected_pce}%, Reported Total={total_pce}%"
                    }]

                    findings.append(PVConsistencyFinding(
                        finding_id=f"PV-TANDEM-FIND-{finding_idx:03d}",
                        rule_id="pv_tandem_current_matching",
                        detector_id="tandem_consistency",
                        risk_level="medium",
                        risk_ceiling="medium",
                        source_file=source_file,
                        table_id=table_id,
                        row_index=row.row_index,
                        device_id=row.device_id,
                        observed_values=observed,
                        recomputed_values=recomputed,
                        tolerance={"abs": 0.3},
                        evidence_items=evidence_items,
                        safe_report_language=safe_lang,
                        alternative_explanations=[
                            "Subcells measured with different aperture areas or mask geometries",
                            "Calibration or spectral mismatch correction discrepancies between subcells",
                            "Rounding or transcription errors in the table",
                            "Top and bottom cell parameters extracted from different individual champion devices"
                        ],
                        false_positive_risks=[
                            "Minor arithmetic differences due to value rounding in reporting tables",
                            "Series vs parallel 4T module wiring not properly specified"
                        ],
                        manual_verification=[
                            "Verify subcell J-V curve datasets and calibration records",
                            "Check if aperture/mask area matches for both measurements",
                            "Confirm the spectral mismatch calculation parameters"
                        ],
                        limitations=[
                            "Relies on correct identification of top, bottom, and total PCE columns"
                        ],
                        metadata={"type": "4t_efficiency_inconsistency", "top_pce": top_pce, "bottom_pce": bottom_pce, "total_pce": total_pce}
                    ))
                    finding_idx += 1

            # Case 2: 2T current matching check
            if is_2t and top_jsc is not None and bottom_jsc is not None:
                min_jsc = min(top_jsc, bottom_jsc)
                if min_jsc > 0:
                    mismatch = abs(top_jsc - bottom_jsc) / min_jsc
                    if mismatch > 0.15:
                        observed = {
                            "top_jsc": top_jsc,
                            "bottom_jsc": bottom_jsc
                        }
                        recomputed = {
                            "current_mismatch_percent": mismatch * 100.0
                        }

                        safe_lang = (
                            f"Candidate tandem PV consistency signal: monolithic 2T tandem subcells indicate a current mismatch "
                            f"of {mismatch*100:.1f}% (Top Jsc={top_jsc} mA/cm², Bottom Jsc={bottom_jsc} mA/cm²). "
                            f"Monolithic 2T tandems are current-limited by the lower-performing subcell. Verify subcell EQE, "
                            f"bias illumination, filtered measurements, and area definitions."
                        )

                        evidence_items = [{
                            "location": f"Row {row.row_index}",
                            "message": f"2T Tandem: Top Jsc={top_jsc} mA/cm2, Bottom Jsc={bottom_jsc} mA/cm2, Mismatch={mismatch*100:.2f}%"
                        }]

                        findings.append(PVConsistencyFinding(
                            finding_id=f"PV-TANDEM-FIND-{finding_idx:03d}",
                            rule_id="pv_tandem_current_matching",
                            detector_id="tandem_consistency",
                            risk_level="medium",
                            risk_ceiling="medium",
                            source_file=source_file,
                            table_id=table_id,
                            row_index=row.row_index,
                            device_id=row.device_id,
                            observed_values=observed,
                            recomputed_values=recomputed,
                            tolerance={"rel": 0.15},
                            evidence_items=evidence_items,
                            safe_report_language=safe_lang,
                            alternative_explanations=[
                                "The subcell values correspond to separately measured single-junction test cells rather than the integrated 2T stack",
                                "The bottom subcell was measured with a filtered light source replicating top cell absorption, but with different calibration",
                                "Varying aperture or mask areas used during separate subcell measurements",
                                "Aperture area of the tandem stack was different from subcell test structures"
                            ],
                            false_positive_risks=[
                                "Subcells are electrically connected in parallel (rare for 2T, but possible in specific designs)",
                                "Wrongly mapped columns for subcell Jsc"
                            ],
                            manual_verification=[
                                "Inspect tandem series/parallel connection architecture",
                                "Review subcell EQE spectra and integrated currents under bias light",
                                "Verify bias illumination spectra and filter dimensions used in testing"
                            ],
                            limitations=[
                                "Assumes series-connected monolithic 2T architecture unless parallel connection is explicitly documented"
                            ],
                            metadata={"type": "2t_current_mismatch", "top_jsc": top_jsc, "bottom_jsc": bottom_jsc, "mismatch": mismatch}
                        ))
                        finding_idx += 1

            # Case 3: 2T reporting completeness warning
            if is_2t:
                # Check for missing bias illumination / bias voltage / filtered EQE columns
                has_bias_info = any(any(k in col for k in ("bias", "filter")) for col in raw_cols_lower)
                has_subcell_jsc = (top_jsc is not None or bottom_jsc is not None)
                
                if not has_bias_info or not has_subcell_jsc:
                    observed = {
                        "has_bias_info": has_bias_info,
                        "has_subcell_jsc_data": has_subcell_jsc
                    }
                    
                    safe_lang = (
                        "PV tandem reporting completeness gap: 2T tandem context detected but subcell current density "
                        "data or measurement bias illumination/voltage parameters are missing from the parsed tables. "
                        "Verify subcell EQE protocols and filtered calibration details in the manuscript methods or SI."
                    )
                    
                    evidence_items = [{
                        "location": f"Table {table_id}",
                        "message": f"Tandem table '{source_file}' is missing subcell Jsc columns or bias light/voltage descriptors."
                    }]

                    findings.append(PVConsistencyFinding(
                        finding_id=f"PV-TANDEM-FIND-{finding_idx:03d}",
                        rule_id="pv_tandem_current_matching",
                        detector_id="tandem_consistency",
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
                            "Measurement details are provided in main text or SI methods rather than the table package",
                            "Device is a simple test stack where subcells were not characterized individually"
                        ],
                        false_positive_risks=[
                            "Table is a high-level summary of champion device PCE only"
                        ],
                        manual_verification=[
                            "Verify the experimental methods for subcell EQE measurement protocols",
                            "Check SI for subcell spectral response and bias voltage curves"
                        ],
                        limitations=[
                            "Cannot parse details described in unstructured text or captions"
                        ],
                        metadata={"type": "tandem_reporting_gap", "has_bias_info": has_bias_info, "has_subcell_jsc": has_subcell_jsc}
                    ))
                    finding_idx += 1

    return findings
