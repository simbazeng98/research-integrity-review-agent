from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.schema import JVCurve, JVMetrics
from integrity_agent.domains.photovoltaics.raw_measurements.jv_hysteresis import pair_forward_reverse_curves, run_jv_hysteresis_check

def test_jv_hysteresis_pairing_and_finding():
    c_fwd = JVCurve(
        curve_id="dev1_fwd", source_file="dev1_fwd.csv",
        voltage_v=[0.0, 1.0], current_density_ma_cm2=[-20.0, 0.0],
        scan_direction="forward", device_id_guess="dev1"
    )
    c_rev = JVCurve(
        curve_id="dev1_rev", source_file="dev1_rev.csv",
        voltage_v=[0.0, 1.0], current_density_ma_cm2=[-20.0, 0.0],
        scan_direction="reverse", device_id_guess="dev1"
    )
    
    m_fwd = JVMetrics(curve_id="dev1_fwd", device_id="dev1", pce_percent=15.0)
    m_rev = JVMetrics(curve_id="dev1_rev", device_id="dev1", pce_percent=17.0) # Delta = 2.0% PCE, HI = 2/17 = 0.117

    # Pair them
    pairs = pair_forward_reverse_curves([c_fwd, c_rev], [m_fwd, m_rev])
    assert len(pairs) == 1
    assert pairs[0].device_id == "dev1"
    assert abs(pairs[0].abs_delta_pce - 2.0) < 1e-5
    
    # Run detector
    findings = run_jv_hysteresis_check(pairs)
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "recalculated PCE values (Forward: 15.00%, Reverse: 17.00%" in findings[0].safe_report_language
    
def test_jv_hysteresis_no_finding_for_small_delta():
    c_fwd = JVCurve(
        curve_id="dev1_fwd", source_file="dev1_fwd.csv",
        voltage_v=[0.0, 1.0], current_density_ma_cm2=[-20.0, 0.0],
        scan_direction="forward", device_id_guess="dev1"
    )
    c_rev = JVCurve(
        curve_id="dev1_rev", source_file="dev1_rev.csv",
        voltage_v=[0.0, 1.0], current_density_ma_cm2=[-20.0, 0.0],
        scan_direction="reverse", device_id_guess="dev1"
    )
    
    m_fwd = JVMetrics(curve_id="dev1_fwd", device_id="dev1", pce_percent=15.0)
    m_rev = JVMetrics(curve_id="dev1_rev", device_id="dev1", pce_percent=15.2) # Delta = 0.2% PCE

    pairs = pair_forward_reverse_curves([c_fwd, c_rev], [m_fwd, m_rev])
    findings = run_jv_hysteresis_check(pairs)
    assert not findings
