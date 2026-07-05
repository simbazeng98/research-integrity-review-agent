from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.stability_reporting import run_pv_stability_reporting_check

def test_stability_reporting_detector():
    # Table with no stability fields or keywords
    row_no_stab = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        voc_v=1.10, raw_values={"Voc": "1.10"}
    )
    findings = run_pv_stability_reporting_check([row_no_stab])
    assert not findings

    # T80 without temp/humidity
    row_t80_incomplete = PVMetricRow(
        row_id="2", source_file="test.csv", table_id="tbl-2", row_index=1,
        t80_h=500.0, raw_values={"t80_h": "500"}
    )
    findings = run_pv_stability_reporting_check([row_t80_incomplete])
    assert len(findings) == 1
    assert findings[0].risk_level == "low"
    assert "temperature conditions" in findings[0].observed_values["missing_conditions"]
    assert "humidity or atmospheric environment" in findings[0].observed_values["missing_conditions"]

    # ISOS-L-2 complete
    row_complete = PVMetricRow(
        row_id="3", source_file="test.csv", table_id="tbl-3", row_index=1,
        t80_h=1000.0, temperature_c=65.0, humidity_percent=50.0,
        mpp_tracking="mpp_tracking", encapsulation="glass-glass",
        stabilized_pce_percent=15.0,
        raw_values={
            "t80_h": "1000", "temperature_c": "65", "humidity_percent": "50",
            "mpp_tracking": "Yes", "encapsulation": "glass", "light": "LED"
        }
    )
    findings = run_pv_stability_reporting_check([row_complete])
    assert not findings
