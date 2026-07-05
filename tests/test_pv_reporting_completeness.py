from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.reporting_completeness import run_pv_reporting_completeness_check

def test_reporting_completeness_detector():
    # Table with no PV fields
    row_no_pv = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        raw_values={"other_field": "123"}
    )
    findings = run_pv_reporting_completeness_check([row_no_pv])
    assert not findings

    # Minimal PV table
    row_min_pv = PVMetricRow(
        row_id="2", source_file="test.csv", table_id="tbl-2", row_index=1,
        voc_v=1.10, jsc_ma_cm2=22.0,
        raw_values={"Voc": "1.10", "Jsc": "22.0"}
    )
    findings = run_pv_reporting_completeness_check([row_min_pv])
    assert len(findings) == 1
    assert findings[0].risk_level == "low"
    assert "PV reporting completeness gap detected" in findings[0].safe_report_language
    obs = findings[0].observed_values
    assert "device area (active/aperture/mask area)" in obs["missing_fields"]
    assert "scan direction (forward/reverse)" in obs["missing_fields"]

    # Tandem table -> requires subcell bias
    row_tandem = PVMetricRow(
        row_id="3", source_file="test.csv", table_id="tbl-3", row_index=1,
        voc_v=1.10, jsc_ma_cm2=22.0,
        raw_values={"Voc": "1.10", "Jsc": "22.0", "tandem_top": "15.0"}
    )
    findings = run_pv_reporting_completeness_check([row_tandem])
    assert len(findings) == 1
    assert "tandem subcell bias illumination or bias voltage" in findings[0].observed_values["missing_fields"]
