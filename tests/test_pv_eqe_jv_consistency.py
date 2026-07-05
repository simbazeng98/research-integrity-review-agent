from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.eqe_jv_consistency import run_eqe_jv_jsc_consistency_check

def test_eqe_jv_consistency_detector():
    # 4% difference
    row_4 = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        jsc_ma_cm2=20.0, eqe_jsc_ma_cm2=19.2
    )
    findings = run_eqe_jv_jsc_consistency_check([row_4])
    assert not findings

    # 8% difference -> low note
    row_8 = PVMetricRow(
        row_id="2", source_file="test.csv", table_id="tbl-1", row_index=2,
        jsc_ma_cm2=20.0, eqe_jsc_ma_cm2=18.4
    )
    findings = run_eqe_jv_jsc_consistency_check([row_8])
    assert len(findings) == 1
    assert findings[0].risk_level == "low"

    # 15% difference -> medium finding
    row_15 = PVMetricRow(
        row_id="3", source_file="test.csv", table_id="tbl-1", row_index=3,
        jsc_ma_cm2=20.0, eqe_jsc_ma_cm2=17.0
    )
    findings = run_eqe_jv_jsc_consistency_check([row_15])
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "integrated EQE-derived Jsc (17.00 mA/cm²) differs from J–V Jsc" in findings[0].safe_report_language

    # Missing EQE Jsc
    row_missing = PVMetricRow(
        row_id="4", source_file="test.csv", table_id="tbl-1", row_index=4,
        jsc_ma_cm2=20.0, eqe_jsc_ma_cm2=None
    )
    findings = run_eqe_jv_jsc_consistency_check([row_missing])
    assert not findings

    # Zero/negative current densities
    row_zero = PVMetricRow(
        row_id="5", source_file="test.csv", table_id="tbl-1", row_index=5,
        jsc_ma_cm2=0.0, eqe_jsc_ma_cm2=18.0
    )
    findings = run_eqe_jv_jsc_consistency_check([row_zero])
    assert not findings
