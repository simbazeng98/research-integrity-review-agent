from __future__ import annotations

import pytest

from integrity_agent.domains.photovoltaics.pce_consistency import (
    run_pce_consistency_check,
)
from integrity_agent.domains.photovoltaics.schema import PVMetricRow


def _multiscan_rows() -> list[PVMetricRow]:
    """Synthetic long-table matrix: intensity x condition x scan direction."""

    cases = [
        # row, Pin, condition, scan, Voc, Jsc, FF, reported PCE, stabilized PCE
        (1, 100.0, "control", "forward", 1.00, 20.0, 0.80, 17.0, None),
        (2, 100.0, "control", "reverse", 1.00, 20.0, 0.80, 16.2, None),
        (3, 100.0, "target", "forward", 1.10, 22.0, 0.75, 18.2, None),
        (4, 100.0, "target", "reverse", 1.10, 22.0, 0.75, 19.0, 18.2),
        (5, 80.0, "control", "forward", 1.00, 20.0, 0.80, 21.0, None),
        (6, 80.0, "control", "reverse", 1.00, 20.0, 0.80, 20.2, None),
        (7, 80.0, "target", "forward", 1.10, 22.0, 0.75, 22.7, None),
        (8, 80.0, "target", "reverse", 1.10, 22.0, 0.75, 24.0, 22.7),
    ]
    return [
        PVMetricRow(
            row_id=f"toy-pv-multiscan-row-{row_index}",
            source_file="pv/toy_multiscan.csv",
            table_id="toy-pv-multiscan",
            row_index=row_index,
            device_id=f"toy-{condition}-{scan}-{int(light_intensity)}",
            condition_label=condition,
            scan_direction=scan,
            voc_v=voc,
            jsc_ma_cm2=jsc,
            ff=ff,
            ff_unit="fraction",
            pce_percent=reported_pce,
            stabilized_pce_percent=stabilized_pce,
            light_intensity_mw_cm2=light_intensity,
            raw_values={
                "Condition": condition,
                "Scan direction": scan,
                "Voc (V)": voc,
                "Jsc (mA/cm2)": jsc,
                "FF": ff,
                "PCE (%)": reported_pce,
                "Stabilized PCE (%)": stabilized_pce,
                "Light intensity (mW/cm2)": light_intensity,
            },
        )
        for (
            row_index,
            light_intensity,
            condition,
            scan,
            voc,
            jsc,
            ff,
            reported_pce,
            stabilized_pce,
        ) in cases
    ]


def test_eight_row_multiscan_matrix_has_four_clear_findings_and_four_tolerated_rows():
    findings = run_pce_consistency_check(_multiscan_rows())

    assert [finding.row_index for finding in findings] == [1, 4, 5, 8]
    assert {finding.risk_level for finding in findings} == {"medium"}
    assert all(finding.tolerance == {"abs": 0.3, "rel": 0.03} for finding in findings)

    # Rows 2, 3, 6 and 7 differ only within the unchanged printed-value
    # tolerance; the detector must not promote them to candidate findings.
    tolerated_rows = {2, 3, 6, 7}
    assert tolerated_rows.isdisjoint(
        {finding.row_index for finding in findings}
    )


def test_multiscan_findings_preserve_row_trace_values_and_explicit_illumination():
    rows_by_index = {row.row_index: row for row in _multiscan_rows()}
    findings = run_pce_consistency_check(list(rows_by_index.values()))
    expected_recomputed = {1: 16.0, 4: 18.15, 5: 20.0, 8: 22.6875}

    for finding in findings:
        row = rows_by_index[finding.row_index]
        assert finding.source_file == "pv/toy_multiscan.csv"
        assert finding.table_id == "toy-pv-multiscan"
        assert finding.device_id == row.device_id
        assert finding.observed_values["pce_percent"] == row.pce_percent
        assert finding.observed_values["light_intensity_mw_cm2"] == (
            row.light_intensity_mw_cm2
        )
        assert finding.recomputed_values["pce_percent"] == pytest.approx(
            expected_recomputed[finding.row_index]
        )
        assert finding.evidence_items[0]["location"] == f"Row {row.row_index}"
        assert (
            f"Pin={row.light_intensity_mw_cm2}mW/cm2"
            in finding.evidence_items[0]["message"]
        )
        assert (
            f"under the specified {row.light_intensity_mw_cm2} mW/cm² illumination basis"
            in finding.safe_report_language
        )


def test_stabilized_only_value_is_not_recomputed_as_scan_pce():
    stabilized_only = PVMetricRow(
        row_id="toy-stabilized-only",
        source_file="pv/toy_multiscan.csv",
        table_id="toy-pv-multiscan",
        row_index=9,
        device_id="toy-stabilized-only",
        voc_v=1.00,
        jsc_ma_cm2=20.0,
        ff=0.80,
        pce_percent=None,
        stabilized_pce_percent=16.0,
        light_intensity_mw_cm2=100.0,
    )

    assert run_pce_consistency_check([stabilized_only]) == []


def test_scan_pce_finding_keeps_stabilized_vs_scan_as_explicit_alternative():
    flagged_row = _multiscan_rows()[3]
    assert flagged_row.stabilized_pce_percent is not None

    finding = run_pce_consistency_check([flagged_row])[0]

    assert any(
        "stabilized power output rather than scan-derived" in alternative.lower()
        for alternative in finding.alternative_explanations
    )
    assert any(
        "stabilized power conversion efficiency" in risk.lower()
        for risk in finding.false_positive_risks
    )
    assert "stabilized or scan-specific" in finding.safe_report_language.lower()
