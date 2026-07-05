from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.tandem_consistency import run_tandem_consistency_check

def test_tandem_consistency_detector():
    # Regular single-junction table (no tandem keywords)
    row_single = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        voc_v=1.10, raw_values={"Voc": "1.10"}
    )
    findings = run_tandem_consistency_check([row_single])
    assert not findings

    # 4T consistent: total PCE = 25%, top = 15%, bottom = 10%
    row_4t_ok = PVMetricRow(
        row_id="2", source_file="test.csv", table_id="tbl-2", row_index=1,
        raw_values={"tandem_architecture": "4T", "top_pce": "15.0", "bottom_pce": "10.0", "total_pce": "25.0"}
    )
    findings = run_tandem_consistency_check([row_4t_ok])
    assert not findings

    # 4T inconsistent: total PCE = 27% > 25.3%
    row_4t_err = PVMetricRow(
        row_id="3", source_file="test.csv", table_id="tbl-3", row_index=1,
        raw_values={"tandem_architecture": "4T", "top_pce": "15.0", "bottom_pce": "10.0", "total_pce": "27.0"}
    )
    findings = run_tandem_consistency_check([row_4t_err])
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "exceeds the sum of top and bottom subcells" in findings[0].safe_report_language

    # 2T current mismatch: top_jsc = 20, bottom_jsc = 15 -> mismatch = 5/15 = 33.3% > 15%
    row_2t_mismatch = PVMetricRow(
        row_id="4", source_file="test.csv", table_id="tbl-4", row_index=1,
        raw_values={"tandem_architecture": "2T", "top_jsc": "20.0", "bottom_jsc": "15.0"}
    )
    findings = run_tandem_consistency_check([row_2t_mismatch])
    # Should yield a mismatch finding (medium) + a completeness finding (low) for lack of bias light info
    assert len(findings) >= 1
    mismatch_f = [f for f in findings if f.risk_level == "medium"]
    assert len(mismatch_f) == 1
    assert "current mismatch of 33.3%" in mismatch_f[0].safe_report_language

    # 2T without subcell data -> completeness warning
    row_2t_incomplete = PVMetricRow(
        row_id="5", source_file="test.csv", table_id="tbl-5", row_index=1,
        raw_values={"tandem_architecture": "2T", "total_pce": "18.0"}
    )
    findings = run_tandem_consistency_check([row_2t_incomplete])
    assert len(findings) == 1
    assert findings[0].risk_level == "low"
    assert "PV tandem reporting completeness gap" in findings[0].safe_report_language
