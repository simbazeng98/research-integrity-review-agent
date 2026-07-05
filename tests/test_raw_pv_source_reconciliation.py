from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.raw_measurements.schema import JVMetrics, EQEIntegrationResult
from integrity_agent.domains.photovoltaics.raw_measurements.source_reconciliation import (
    reconcile_jv_metrics_with_reported, reconcile_eqe_with_reported, reconcile_eqe_with_jv
)

def test_reconcile_jv_metrics_mismatch():
    reported = [
        PVMetricRow(
            row_id="rep-1", source_file="paper.csv", table_id="tbl-1", row_index=1,
            device_id="dev1", voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=18.15
        )
    ]
    # PCE mismatch (18.15% reported vs 15.0% recomputed)
    recalculated = [
        JVMetrics(
            curve_id="dev1_fwd", device_id="dev1", voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=15.0
        )
    ]
    
    findings = reconcile_jv_metrics_with_reported(recalculated, reported)
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "PCE (reported: 18.15%, recalculated: 15.00%)" in findings[0].safe_report_language

def test_reconcile_eqe_metrics_mismatch():
    reported = [
        PVMetricRow(
            row_id="rep-1", source_file="paper.csv", table_id="tbl-1", row_index=1,
            device_id="dev1", eqe_jsc_ma_cm2=22.0
        )
    ]
    recalculated_eqe = [
        EQEIntegrationResult(
            spectrum_id="dev1_eqe", device_id="dev1", integrated_jsc_ma_cm2=18.0
        )
    ]
    
    findings = reconcile_eqe_with_reported(recalculated_eqe, reported)
    assert len(findings) == 1
    assert "differs from reported EQE Jsc (22.00 mA/cm²)" in findings[0].safe_report_language

def test_reconcile_eqe_with_jv_mismatch():
    recalculated_eqe = [
        EQEIntegrationResult(
            spectrum_id="dev1_eqe", device_id="dev1", integrated_jsc_ma_cm2=17.0
        )
    ]
    recalculated_jv = [
        JVMetrics(
            curve_id="dev1_fwd", device_id="dev1", jsc_ma_cm2=20.0
        )
    ]
    
    findings = reconcile_eqe_with_jv(recalculated_eqe, recalculated_jv)
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "differs from recomputed J–V Jsc (20.00 mA/cm²) by 15.0%" in findings[0].safe_report_language
