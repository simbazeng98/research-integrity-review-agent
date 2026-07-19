from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVFieldMapping, PVConsistencyFinding

def test_pv_schema_dataclasses():
    row = PVMetricRow(
        row_id="tbl-001-row-1",
        source_file="test.csv",
        table_id="tbl-001",
        row_index=1,
        voc_v=1.10,
        jsc_ma_cm2=22.0,
        ff=0.75,
        pce_percent=18.15
    )
    r_dict = row.to_dict()
    assert r_dict["row_id"] == "tbl-001-row-1"
    assert r_dict["voc_v"] == 1.10
    assert r_dict["pce_percent"] == 18.15

    fm = PVFieldMapping(
        canonical_field="voc_v",
        matched_column="Voc (V)",
        confidence=0.95,
        unit_hint="v"
    )
    f_dict = fm.to_dict()
    assert f_dict["canonical_field"] == "voc_v"
    assert f_dict["confidence"] == 0.95

    finding = PVConsistencyFinding(
        finding_id="PV-FIND-001",
        rule_id="pv_pce_consistency",
        detector_id="pce_consistency",
        risk_level="medium",
        risk_ceiling="medium",
        source_file="test.csv",
        table_id="tbl-001"
    )
    find_dict = finding.to_dict()
    assert find_dict["finding_id"] == "PV-FIND-001"
