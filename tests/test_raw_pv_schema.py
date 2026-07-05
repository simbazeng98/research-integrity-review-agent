from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.schema import (
    JVCurve, JVMetrics, JVHysteresisPair, EQESpectrum, EQEIntegrationResult,
    ExcelFormulaAuditItem, RawPVConsistencyFinding
)

def test_raw_pv_schema_to_dict():
    curve = JVCurve(
        curve_id="curve-1",
        source_file="file1.csv",
        voltage_v=[0.0, 1.0],
        current_density_ma_cm2=[-10.0, 0.0],
        scan_direction="forward",
        device_id_guess="dev1",
        warnings=[]
    )
    d = curve.to_dict()
    assert d["curve_id"] == "curve-1"
    assert d["scan_direction"] == "forward"

    metrics = JVMetrics(
        curve_id="curve-1",
        device_id="dev1",
        voc_v=1.0,
        jsc_ma_cm2=10.0,
        ff=0.75,
        pce_percent=7.5,
        warnings=[]
    )
    d = metrics.to_dict()
    assert d["voc_v"] == 1.0
    assert d["pce_percent"] == 7.5

    pair = JVHysteresisPair(
        pair_id="pair-1",
        device_id="dev1",
        forward_curve=curve,
        reverse_curve=curve,
        forward_metrics=metrics,
        reverse_metrics=metrics,
        hysteresis_index=0.0,
        abs_delta_pce=0.0,
        warnings=[]
    )
    d = pair.to_dict()
    assert d["pair_id"] == "pair-1"
    assert d["hysteresis_index"] == 0.0

    eqe = EQESpectrum(
        spectrum_id="eqe-1",
        source_file="eqe.csv",
        wavelength_nm=[400.0, 500.0],
        eqe_fraction=[0.8, 0.85],
        device_id_guess="dev1",
        warnings=[]
    )
    d = eqe.to_dict()
    assert d["spectrum_id"] == "eqe-1"
    assert d["eqe_fraction"] == [0.8, 0.85]

    eqe_res = EQEIntegrationResult(
        spectrum_id="eqe-1",
        device_id="dev1",
        integrated_jsc_ma_cm2=22.0,
        warnings=[]
    )
    d = eqe_res.to_dict()
    assert d["integrated_jsc_ma_cm2"] == 22.0

    audit = ExcelFormulaAuditItem(
        audit_id="audit-1",
        source_file="sheet.xlsx",
        sheet_name="Summary",
        cell_coordinate="E2",
        formula="=B2*C2",
        cached_value=15.0,
        cell_value="=B2*C2",
        audit_type="formula_cell",
        message="test",
        severity="low"
    )
    d = audit.to_dict()
    assert d["audit_id"] == "audit-1"
    assert d["cached_value"] == 15.0

    finding = RawPVConsistencyFinding(
        finding_id="RAW-PV-FIND-001",
        rule_id="pv_jv_hysteresis_candidate",
        detector_id="jv_hysteresis",
        risk_level="medium",
        source_file="file1.csv",
        device_id="dev1",
        observed_values={"fwd": 15.0},
        recomputed_values={"rev": 17.0},
        safe_report_language="mismatch"
    )
    d = finding.to_dict()
    assert d["finding_id"] == "RAW-PV-FIND-001"
    assert d["rule_id"] == "pv_jv_hysteresis_candidate"
