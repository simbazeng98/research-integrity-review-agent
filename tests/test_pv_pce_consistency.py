from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.pce_consistency import run_pce_consistency_check

def test_pce_consistency_detector():
    # Consistent row
    row_ok = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=18.15
    )
    findings = run_pce_consistency_check([row_ok])
    assert not findings

    # Inconsistent row
    row_err = PVMetricRow(
        row_id="2", source_file="test.csv", table_id="tbl-1", row_index=2,
        voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=25.0
    )
    findings = run_pce_consistency_check([row_err])
    assert len(findings) == 1
    assert findings[0].rule_id == "pv_pce_consistency"
    assert findings[0].risk_level == "medium"
    assert "reported PCE (25.0%) differs from recomputed Voc" in findings[0].safe_report_language

    # FF percent vs fraction checks are covered in normalization when building rows,
    # but let's check consistent calculated values in detector.
    row_ff_percent = PVMetricRow(
        row_id="3", source_file="test.csv", table_id="tbl-1", row_index=3,
        voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=18.15, ff_unit="%"
    )
    findings = run_pce_consistency_check([row_ff_percent])
    assert not findings

    # Missing fields
    row_missing = PVMetricRow(
        row_id="4", source_file="test.csv", table_id="tbl-1", row_index=4,
        voc_v=1.10, jsc_ma_cm2=None, ff=0.75, pce_percent=18.15
    )
    findings = run_pce_consistency_check([row_missing])
    assert not findings

    # Non-1-sun consistent row
    row_non_sun_ok = PVMetricRow(
        row_id="5", source_file="test.csv", table_id="tbl-1", row_index=5,
        voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=22.6875, light_intensity_mw_cm2=80.0
    )
    findings = run_pce_consistency_check([row_non_sun_ok])
    assert not findings

    # Non-1-sun inconsistent row
    row_non_sun_err = PVMetricRow(
        row_id="6", source_file="test.csv", table_id="tbl-1", row_index=6,
        voc_v=1.10, jsc_ma_cm2=22.0, ff=0.75, pce_percent=18.15, light_intensity_mw_cm2=80.0
    )
    findings = run_pce_consistency_check([row_non_sun_err])
    assert len(findings) == 1
    assert "under the specified 80.0 mW/cm² illumination basis" in findings[0].safe_report_language
