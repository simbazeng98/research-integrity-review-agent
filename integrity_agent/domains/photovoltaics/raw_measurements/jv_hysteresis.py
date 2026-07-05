from __future__ import annotations

import math
from integrity_agent.domains.photovoltaics.raw_measurements.schema import (
    JVCurve, JVMetrics, JVHysteresisPair, RawPVConsistencyFinding
)

def pair_forward_reverse_curves(curves: list[JVCurve], metrics_list: list[JVMetrics]) -> list[JVHysteresisPair]:
    metrics_map = {m.curve_id: m for m in metrics_list}
    pairs = []
    
    # Group by device id guess
    device_groups: dict[str, list[JVCurve]] = {}
    unpaired_curves = []
    
    for c in curves:
        dev_id = c.device_id_guess or "unknown"
        if dev_id == "unknown":
            unpaired_curves.append(c)
        else:
            device_groups.setdefault(dev_id, []).append(c)
            
    # Pair grouped devices
    pair_counter = 1
    for dev_id, dev_curves in device_groups.items():
        fwd_curves = [c for c in dev_curves if c.scan_direction == "forward"]
        rev_curves = [c for c in dev_curves if c.scan_direction == "reverse"]
        
        # Match them
        min_len = min(len(fwd_curves), len(rev_curves))
        for i in range(min_len):
            fc = fwd_curves[i]
            rc = rev_curves[i]
            fm = metrics_map.get(fc.curve_id)
            rm = metrics_map.get(rc.curve_id)
            
            if fm and rm and fm.pce_percent is not None and rm.pce_percent is not None:
                pce_f = fm.pce_percent
                pce_r = rm.pce_percent
                max_pce = max(pce_f, pce_r)
                
                hi = (pce_r - pce_f) / max_pce if max_pce > 0 else 0.0
                abs_delta = abs(pce_r - pce_f)
                
                pairs.append(JVHysteresisPair(
                    pair_id=f"pair-{pair_counter:03d}",
                    device_id=dev_id,
                    forward_curve=fc,
                    reverse_curve=rc,
                    forward_metrics=fm,
                    reverse_metrics=rm,
                    hysteresis_index=hi,
                    abs_delta_pce=abs_delta,
                    warnings=[]
                ))
                pair_counter += 1

    # Also try name-based heuristics for unpaired curves
    # E.g. if filenames differ only by fwd/rev
    fwd_unpaired = [c for c in unpaired_curves if c.scan_direction == "forward"]
    rev_unpaired = [c for c in unpaired_curves if c.scan_direction == "reverse"]
    
    for fc in list(fwd_unpaired):
        fc_clean = fc.source_file.lower().replace("forward", "").replace("fwd", "")
        for rc in list(rev_unpaired):
            rc_clean = rc.source_file.lower().replace("reverse", "").replace("rev", "")
            if fc_clean == rc_clean:
                fm = metrics_map.get(fc.curve_id)
                rm = metrics_map.get(rc.curve_id)
                if fm and rm and fm.pce_percent is not None and rm.pce_percent is not None:
                    pce_f = fm.pce_percent
                    pce_r = rm.pce_percent
                    max_pce = max(pce_f, pce_r)
                    
                    hi = (pce_r - pce_f) / max_pce if max_pce > 0 else 0.0
                    abs_delta = abs(pce_r - pce_f)
                    
                    pairs.append(JVHysteresisPair(
                        pair_id=f"pair-{pair_counter:03d}",
                        device_id=fc.device_id_guess or "unknown",
                        forward_curve=fc,
                        reverse_curve=rc,
                        forward_metrics=fm,
                        reverse_metrics=rm,
                        hysteresis_index=hi,
                        abs_delta_pce=abs_delta,
                        warnings=["filename pairing only"]
                    ))
                    pair_counter += 1
                    fwd_unpaired.remove(fc)
                    rev_unpaired.remove(rc)
                    break
                    
    return pairs

def run_jv_hysteresis_check(pairs: list[JVHysteresisPair]) -> list[RawPVConsistencyFinding]:
    findings = []
    for pair in pairs:
        hi = pair.hysteresis_index
        abs_delta = pair.abs_delta_pce
        
        # Trigger finding if abs_delta > 1.0 or abs(hi) > 0.05
        if abs_delta > 1.0 or abs(hi) > 0.05:
            # Set risk level: medium if delta > 1.5 or hi > 0.1, else low
            risk_level = "medium" if (abs_delta > 1.5 or abs(hi) > 0.1) else "low"
            
            fwd_pce = pair.forward_metrics.pce_percent
            rev_pce = pair.reverse_metrics.pce_percent
            
            safe_lang = (
                f"Candidate J–V hysteresis signal: forward and reverse scans for the same parsed device "
                f"yield different recalculated PCE values (Forward: {fwd_pce:.2f}%, Reverse: {rev_pce:.2f}%, "
                f"Hysteresis Index: {hi:.2f}, Abs Delta: {abs_delta:.2f}%). Verify scan direction, scan rate, "
                f"preconditioning, delay time, stabilization, and whether the reported metric is scan-derived or stabilized."
            )
            
            findings.append(RawPVConsistencyFinding(
                finding_id=f"RAW-PV-FIND-{pair.pair_id}",
                rule_id="pv_jv_hysteresis_candidate",
                detector_id="jv_hysteresis",
                risk_level=risk_level,
                risk_ceiling="medium",
                source_file=pair.forward_curve.source_file,
                device_id=pair.device_id,
                observed_values={
                    "forward_pce": fwd_pce,
                    "reverse_pce": rev_pce,
                    "hysteresis_index": hi,
                    "abs_delta_pce": abs_delta
                },
                recomputed_values={
                    "hysteresis_index": hi,
                    "abs_delta_pce": abs_delta
                },
                tolerance={
                    "abs_delta_pce": 1.0,
                    "hysteresis_index": 0.05
                },
                evidence_items=[{
                    "location": f"Device {pair.device_id}",
                    "message": f"Forward PCE: {fwd_pce:.2f}%, Reverse PCE: {rev_pce:.2f}%, Hysteresis Index: {hi:.2f}, Abs Delta: {abs_delta:.2f}%"
                }],
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "legitimate hysteresis",
                    "different scan rates",
                    "preconditioning differences",
                    "device degradation between scans",
                    "parser paired wrong curves",
                    "sign convention / area mismatch",
                    "stabilized PCE reported separately"
                ],
                false_positive_risks=[
                    "Legitimate high hysteresis in perovskite solar cells without any data inconsistency",
                    "Measurement delay or scan speed settings causing standard capacitive current variations"
                ],
                manual_verification=[
                    "raw forward/reverse J–V files",
                    "scan protocol",
                    "scan rate",
                    "delay time",
                    "preconditioning",
                    "MPP tracking",
                    "measurement order",
                    "device ID mapping"
                ],
                limitations=[
                    "Hysteresis pairing relies on filename heuristics or device ID metadata"
                ],
                metadata={
                    "forward_curve_id": pair.forward_curve.curve_id,
                    "reverse_curve_id": pair.reverse_curve.curve_id
                }
            ))
            
    return findings
