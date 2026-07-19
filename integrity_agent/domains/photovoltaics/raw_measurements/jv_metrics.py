from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.schema import JVCurve, JVMetrics

def interpolate_linear(x_list: list[float], y_list: list[float], target_x: float) -> float | None:
    if len(x_list) < 2:
        return None
    for i in range(len(x_list) - 1):
        x1, x2 = x_list[i], x_list[i+1]
        y1, y2 = y_list[i], y_list[i+1]
        if (x1 <= target_x <= x2) or (x2 <= target_x <= x1):
            if x1 == x2:
                return y1
            return y1 + (target_x - x1) * (y2 - y1) / (x2 - x1)
    return None

def extract_jv_metrics(curve: JVCurve, pin_mw_cm2: float = 100.0) -> JVMetrics:
    warnings = list(curve.warnings)
    device_id = curve.device_id_guess or "unknown"
    
    voltages = curve.voltage_v
    currents = curve.current_density_ma_cm2

    if not voltages or not currents or len(voltages) != len(currents):
        return JVMetrics(
            curve_id=curve.curve_id,
            device_id=device_id,
            warnings=warnings + ["Missing or mismatched voltage/current data"]
        )

    # Check for too few points
    if len(voltages) < 5:
        warnings.append("too few points")

    # Check for non-monotonic voltage sweep
    is_ascending = all(voltages[i] <= voltages[i+1] for i in range(len(voltages)-1))
    is_descending = all(voltages[i] >= voltages[i+1] for i in range(len(voltages)-1))
    if not (is_ascending or is_descending):
        warnings.append("non-monotonic voltage sweep")

    # Interpolate Jsc at V = 0
    jsc = None
    has_v_crossing = any((voltages[i] <= 0 <= voltages[i+1]) or (voltages[i+1] <= 0 <= voltages[i]) for i in range(len(voltages)-1))
    if has_v_crossing:
        jsc_val = interpolate_linear(voltages, currents, 0.0)
        if jsc_val is not None:
            jsc = abs(jsc_val)
    else:
        # find closest to V=0
        closest_idx = min(range(len(voltages)), key=lambda idx: abs(voltages[idx]))
        jsc = abs(currents[closest_idx])
        warnings.append("no voltage zero crossing")

    # Interpolate Voc at J = 0
    voc = None
    has_j_crossing = any((currents[i] <= 0 <= currents[i+1]) or (currents[i+1] <= 0 <= currents[i]) for i in range(len(currents)-1))
    if has_j_crossing:
        voc_val = interpolate_linear(currents, voltages, 0.0)
        if voc_val is not None:
            voc = abs(voc_val)
    else:
        # find closest to J=0
        closest_idx = min(range(len(currents)), key=lambda idx: abs(currents[idx]))
        voc = abs(voltages[closest_idx])
        warnings.append("no current zero crossing")

    # Sign convention for power calculation
    # In power generation quadrant, V and J have opposite signs in diode convention (V > 0, J < 0),
    # and same signs in PV convention (V > 0, J > 0).
    
    # Detect sign convention from current at V=0
    jsc_val = interpolate_linear(voltages, currents, 0.0)
    if jsc_val is None and currents:
        jsc_val = currents[0]
        
    is_diode_conv = False
    if jsc_val is not None and jsc_val < 0:
        is_diode_conv = True

    pmp = 0.0
    vmp = None
    jmp = None

    if is_diode_conv:
        # Inferred diode sign convention (current is negative under illumination)
        # Power is generated when V > 0 and J < 0, so P = -V * J > 0
        p_diode = [-v * j if (v > 0 and j < 0) else 0.0 for v, j in zip(voltages, currents)]
        max_diode = max(p_diode) if p_diode else 0.0
        pmp = max_diode
        mpp_idx = p_diode.index(pmp)
        vmp = voltages[mpp_idx]
        jmp = currents[mpp_idx]
        warnings.append("sign convention inferred")
    else:
        # PV sign convention
        # Power is generated when V > 0 and J > 0, so P = V * J > 0
        p_pv = [v * j if (v > 0 and j > 0) else 0.0 for v, j in zip(voltages, currents)]
        max_pv = max(p_pv) if p_pv else 0.0
        pmp = max_pv
        mpp_idx = p_pv.index(pmp)
        vmp = voltages[mpp_idx]
        jmp = currents[mpp_idx]

    if pmp <= 0:
        warnings.append("negative pce after sign normalization")
        pmp = 0.0
        ff = 0.0
        pce = 0.0
    else:
        # FF calculation
        if voc and jsc and (voc * jsc) > 0:
            ff = pmp / (voc * jsc)
        else:
            ff = 0.0
        
        # PCE calculation
        pce = (pmp / pin_mw_cm2) * 100.0

    # Validation checks for realistic metrics
    if voc and (voc > 3.0 or voc < 0.0):
        warnings.append("unrealistic metric")
    if jsc and (jsc > 100.0 or jsc < 0.0):
        warnings.append("unrealistic metric")
    if ff and (ff > 1.0 or ff < 0.0):
        warnings.append("unrealistic metric")
    if pce and (pce > 50.0 or pce < 0.0):
        warnings.append("unrealistic metric")

    return JVMetrics(
        curve_id=curve.curve_id,
        device_id=device_id,
        voc_v=voc,
        jsc_ma_cm2=jsc,
        ff=ff,
        pce_percent=pce,
        vmp_v=vmp,
        jmp_ma_cm2=jmp,
        pmp_mw_cm2=pmp,
        warnings=warnings
    )
