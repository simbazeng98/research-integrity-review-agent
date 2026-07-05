from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.schema import JVCurve
from integrity_agent.domains.photovoltaics.raw_measurements.jv_metrics import extract_jv_metrics

def test_extract_jv_metrics_normal():
    # Normal curve under diode convention (current is negative in IV quadrant)
    # Voc = 1.10V, Jsc = 22.0 mA/cm2, peak power at V=0.9, J=-18.0 -> Pmp = 16.2
    # FF = 16.2 / (1.1 * 22.0) = 0.6694, PCE = 16.2%
    curve = JVCurve(
        curve_id="dev1_fwd",
        source_file="dev1_fwd.csv",
        voltage_v=[-0.2, -0.1, 0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.1, 1.2],
        current_density_ma_cm2=[-22.2, -22.1, -22.0, -21.9, -21.8, -21.5, -21.0, -20.0, -18.0, -12.0, 0.0, 20.0],
        scan_direction="forward",
        device_id_guess="dev1"
    )
    
    metrics = extract_jv_metrics(curve)
    assert abs(metrics.voc_v - 1.10) < 1e-5
    assert abs(metrics.jsc_ma_cm2 - 22.0) < 1e-5
    assert abs(metrics.pce_percent - 16.20) < 1e-5
    assert abs(metrics.ff - 0.66942) < 1e-4
    assert "sign convention inferred" in metrics.warnings

def test_extract_jv_metrics_no_zero_crossings():
    # Curve completely shifted, V starts at 0.1, J is always negative
    curve = JVCurve(
        curve_id="dev2_fwd",
        source_file="dev2_fwd.csv",
        voltage_v=[0.1, 0.2, 0.3],
        current_density_ma_cm2=[-20.0, -18.0, -15.0],
        scan_direction="forward"
    )
    
    metrics = extract_jv_metrics(curve)
    assert "no voltage zero crossing" in metrics.warnings
    assert "no current zero crossing" in metrics.warnings
    # Estimated Voc/Jsc from closest points
    assert metrics.jsc_ma_cm2 == 20.0  # closest V to 0 is 0.1, J is -20.0
    assert metrics.voc_v == 0.3  # closest J to 0 is -15.0, V is 0.3

def test_extract_jv_metrics_sparse_and_non_monotonic():
    # Sparse curve (< 5 points) and non-monotonic voltage
    curve = JVCurve(
        curve_id="dev3_fwd",
        source_file="dev3_fwd.csv",
        voltage_v=[0.0, 0.5, 0.2],
        current_density_ma_cm2=[-20.0, -15.0, -18.0]
    )
    
    metrics = extract_jv_metrics(curve)
    assert "too few points" in metrics.warnings
    assert "non-monotonic voltage sweep" in metrics.warnings
