from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.voc_loss import run_voc_loss_check

def test_voc_loss_detector():
    # Normal Voc loss
    row_normal = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        bandgap_ev=1.78, voc_v=1.20
    )
    findings = run_voc_loss_check([row_normal])
    assert not findings

    # Negative/suspicious Voc loss (Voc > Eg)
    row_neg = PVMetricRow(
        row_id="2", source_file="test.csv", table_id="tbl-1", row_index=2,
        bandgap_ev=1.78, voc_v=1.85
    )
    findings = run_voc_loss_check([row_neg])
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "imply an unusual or negative Voc loss" in findings[0].safe_report_language

    # High Voc loss (low risk note)
    row_high = PVMetricRow(
        row_id="3", source_file="test.csv", table_id="tbl-1", row_index=3,
        bandgap_ev=1.78, voc_v=0.90
    )
    findings = run_voc_loss_check([row_high])
    assert len(findings) == 1
    assert findings[0].risk_level == "low"
    assert "indicate a high Voc loss" in findings[0].safe_report_language

    # Unnormalized Voc (e.g. mV reported as V)
    row_mv = PVMetricRow(
        row_id="4", source_file="test.csv", table_id="tbl-1", row_index=4,
        bandgap_ev=1.78, voc_v=1200.0
    )
    findings = run_voc_loss_check([row_mv])
    assert len(findings) == 1
    assert findings[0].risk_level == "medium"
    assert "unusually large" in findings[0].safe_report_language
