from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding

def run_voc_loss_check(
    rows: list[PVMetricRow],
    warning_loss_threshold: float = 0.65,
    suspicious_low_loss_threshold: float = 0.05
) -> list[PVConsistencyFinding]:
    findings: list[PVConsistencyFinding] = []
    finding_idx = 1

    for row in rows:
        if row.bandgap_ev is None or row.voc_v is None:
            continue

        bandgap = row.bandgap_ev
        voc = row.voc_v

        # Check for unnormalized Voc in mV (e.g. Voc = 1200)
        # If Voc is very large, it's likely mV or a typo.
        if voc > 10.0:
            # Output a finding for unit issue
            observed = {"voc_v": voc, "bandgap_ev": bandgap}
            safe_lang = (
                f"Candidate PV physical-consistency signal: reported Voc ({voc}) is unusually large, "
                f"suggesting a unit mapping issue (e.g., Voc reported in mV instead of V)."
            )
            evidence_items = [{
                "location": f"Row {row.row_index}",
                "message": f"Voc={voc} is > 10V, which is physically implausible for single-junction cells."
            }]
            finding = PVConsistencyFinding(
                finding_id=f"PV-VOC-LOSS-FIND-{finding_idx:03d}",
                rule_id="pv_voc_loss_consistency",
                detector_id="voc_loss",
                risk_level="medium",
                risk_ceiling="medium",
                source_file=row.source_file,
                table_id=row.table_id,
                row_index=row.row_index,
                device_id=row.device_id,
                observed_values=observed,
                recomputed_values={},
                tolerance=None,
                evidence_items=evidence_items,
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "Voc was reported in mV but the column unit was not parsed or was incorrectly labeled as V",
                    "Tandem cell modules connected in series, multiplying the Voc",
                    "Typographical error in data entry"
                ],
                false_positive_risks=[
                    "Large multi-junction PV modules with high series-connected cell count",
                    "Incorrect unit normalization or field mapping"
                ],
                manual_verification=[
                    "Verify the unit label of the Voc column in the source table",
                    "Check if the device is a single junction cell or series-connected tandem module",
                    "Check the manuscript for the correct Voc value and unit"
                ],
                limitations=[
                    "Assumes single-junction device behavior unless series connection/tandem module is specified"
                ],
                metadata={"voc": voc, "bandgap": bandgap, "issue": "unusually_large_voc"}
            )
            findings.append(finding)
            finding_idx += 1
            continue

        voc_loss = bandgap - voc
        
        # Check for negative or near-zero Voc loss (physically suspicious)
        if voc_loss < suspicious_low_loss_threshold:
            observed = {"voc_v": voc, "bandgap_ev": bandgap}
            recomputed = {"voc_loss": voc_loss}
            safe_lang = (
                f"Candidate PV physical-consistency signal: reported bandgap ({bandgap} eV) and Voc ({voc} V) "
                f"imply an unusual or negative Voc loss ({voc_loss:.4f} eV). Verify units, field mapping, "
                f"bandgap measurement method, device architecture, and whether Voc corresponds to the same device."
            )
            evidence_items = [{
                "location": f"Row {row.row_index}",
                "message": f"Bandgap: {bandgap} eV, Voc: {voc} V, Implied Voc Loss: {voc_loss:.4f} eV"
            }]

            finding = PVConsistencyFinding(
                finding_id=f"PV-VOC-LOSS-FIND-{finding_idx:03d}",
                rule_id="pv_voc_loss_consistency",
                detector_id="voc_loss",
                risk_level="medium",
                risk_ceiling="medium",
                source_file=row.source_file,
                table_id=row.table_id,
                row_index=row.row_index,
                device_id=row.device_id,
                observed_values=observed,
                recomputed_values=recomputed,
                tolerance={"suspicious_low_loss_threshold": suspicious_low_loss_threshold},
                evidence_items=evidence_items,
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "Bandgap measured from a different film or condition than the device J-V characteristics",
                    "Optical bandgap (from absorption edge) differs from electronic bandgap",
                    "Tandem subcell mismatch or incorrect mapping of subcell Voc",
                    "Unit mapping issue where Voc was in mV but mapped as V",
                    "Typographical error in table values"
                ],
                false_positive_risks=[
                    "High-efficiency tandems or multi-junction devices",
                    "Alternative definitions of bandgap (e.g. high-energy PL peak)",
                    "Data mapping error from non-PV metric column"
                ],
                manual_verification=[
                    "Check the absorption/PL/Tauc plot source data to verify the bandgap extraction",
                    "Inspect raw J-V curves for the correct Voc value",
                    "Confirm the device structure and scan protocols",
                    "Verify if bandgap and Voc are from the exact same device and film composition"
                ],
                limitations=[
                    "Relies on correct mapping of both bandgap and Voc columns"
                ],
                metadata={"voc": voc, "bandgap": bandgap, "voc_loss": voc_loss, "issue": "suspicious_low_voc_loss"}
            )
            findings.append(finding)
            finding_idx += 1

        # Check for very high Voc loss (low risk note, not misconduct)
        elif voc_loss > warning_loss_threshold:
            observed = {"voc_v": voc, "bandgap_ev": bandgap}
            recomputed = {"voc_loss": voc_loss}
            safe_lang = (
                f"PV performance note: reported bandgap ({bandgap} eV) and Voc ({voc} V) "
                f"indicate a high Voc loss ({voc_loss:.4f} eV). This does not indicate misconduct; "
                f"high Voc loss is common in many materials, particularly wide-bandgap absorbers or newer compositions."
            )
            evidence_items = [{
                "location": f"Row {row.row_index}",
                "message": f"Bandgap: {bandgap} eV, Voc: {voc} V, Implied Voc Loss: {voc_loss:.4f} eV"
            }]

            finding = PVConsistencyFinding(
                finding_id=f"PV-VOC-LOSS-FIND-{finding_idx:03d}",
                rule_id="pv_voc_loss_consistency",
                detector_id="voc_loss",
                risk_level="low",
                risk_ceiling="low",
                source_file=row.source_file,
                table_id=row.table_id,
                row_index=row.row_index,
                device_id=row.device_id,
                observed_values=observed,
                recomputed_values=recomputed,
                tolerance={"warning_loss_threshold": warning_loss_threshold},
                evidence_items=evidence_items,
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "High interfacial recombination or bulk recombination in the absorber",
                    "Energetic offsets at the transport layer interfaces",
                    "Unoptimized contact materials or defective films",
                    "Wide-bandgap perovskite materials which naturally exhibit higher Voc loss"
                ],
                false_positive_risks=[
                    "Normal performance trait for low-efficiency or novel material devices"
                ],
                manual_verification=[
                    "Verify alignment of energy levels at device heterojunctions",
                    "Review literature benchmarks for similar material systems"
                ],
                limitations=[
                    "This is a performance note, not a quality or integrity check"
                ],
                metadata={"voc": voc, "bandgap": bandgap, "voc_loss": voc_loss, "issue": "high_voc_loss"}
            )
            findings.append(finding)
            finding_idx += 1

    return findings
