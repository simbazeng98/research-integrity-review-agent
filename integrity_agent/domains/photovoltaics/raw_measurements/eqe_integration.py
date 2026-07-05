from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.schema import EQESpectrum, EQEIntegrationResult
from integrity_agent.domains.photovoltaics.raw_measurements.jv_metrics import interpolate_linear

def integrate_eqe_jsc(spectrum: EQESpectrum, reference_spectrum: list[tuple[float, float]]) -> EQEIntegrationResult:
    warnings = list(spectrum.warnings)
    device_id = spectrum.device_id_guess or "unknown"

    w_meas = spectrum.wavelength_nm
    eqe_fraction = spectrum.eqe_fraction

    if not w_meas or not eqe_fraction:
        return EQEIntegrationResult(
            spectrum_id=spectrum.spectrum_id,
            device_id=device_id,
            integrated_jsc_ma_cm2=0.0,
            warnings=warnings + ["Missing or empty EQE data"]
        )

    # Sort measured spectrum just in case
    meas_points = sorted(zip(w_meas, eqe_fraction), key=lambda x: x[0])
    w_meas_sorted = [p[0] for p in meas_points]
    eqe_fraction_sorted = [p[1] for p in meas_points]

    # Constants
    # Current density Jsc (mA/cm2) = q / (10 * h * c) * 1e-9 * ∫ EQE(λ) * E(λ) * λ * dλ
    # multiplier = 1.602176634e-19 / (10.0 * 6.62607015e-34 * 2.99792458e8) * 1e-9 = 8.0655446e-5
    CONST_MULTIPLIER = 8.0655446e-5

    # Interpolate EQE on reference spectrum points
    # Integrate using trapezoidal rule
    integrated_jsc = 0.0
    
    # We will compute integrand at each reference wavelength point
    integrand_points = []
    
    for w_ref, irr_ref in reference_spectrum:
        # Interpolate EQE at w_ref, but do not extrapolate (assume 0 outside measured range)
        if w_ref < w_meas_sorted[0] or w_ref > w_meas_sorted[-1]:
            eqe_val = 0.0
        else:
            eqe_val = interpolate_linear(w_meas_sorted, eqe_fraction_sorted, w_ref)
            if eqe_val is None:
                eqe_val = 0.0
        
        # Calculate contribution value
        val = eqe_val * irr_ref * w_ref * CONST_MULTIPLIER
        integrand_points.append((w_ref, val))

    # Apply trapezoidal rule
    for i in range(len(integrand_points) - 1):
        w1, val1 = integrand_points[i]
        w2, val2 = integrand_points[i+1]
        dw = w2 - w1
        integrated_jsc += 0.5 * (val1 + val2) * dw

    # Checks & Warnings
    if len(w_meas_sorted) < 15:
        warnings.append("sparse wavelength grid")
        
    meas_min = w_meas_sorted[0]
    meas_max = w_meas_sorted[-1]
    if meas_min > 350.0 or meas_max < 900.0:
        warnings.append("measured range narrower than reference range")
        
    if any(e < -0.05 or e > 1.05 for e in eqe_fraction_sorted):
        warnings.append("EQE values outside physical range")
        
    if integrated_jsc < 5.0 or integrated_jsc > 50.0:
        warnings.append("integrated Jsc unusual high/low")

    return EQEIntegrationResult(
        spectrum_id=spectrum.spectrum_id,
        device_id=device_id,
        integrated_jsc_ma_cm2=integrated_jsc,
        warnings=warnings
    )
