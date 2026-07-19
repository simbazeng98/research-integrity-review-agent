from __future__ import annotations

from integrity_agent.domains.photovoltaics.schema import PVMetricRow
from integrity_agent.domains.photovoltaics.materials_characterization import run_materials_characterization_check

def test_materials_characterization_detector():
    # Generic PV metrics table (no materials characterization keywords)
    row_pv = PVMetricRow(
        row_id="1", source_file="test.csv", table_id="tbl-1", row_index=1,
        voc_v=1.10, raw_values={"Voc": "1.10"}
    )
    findings = run_materials_characterization_check([row_pv])
    assert not findings

    # XRD table with missing radiation source
    row_xrd = PVMetricRow(
        row_id="2", source_file="xrd_results.csv", table_id="tbl-2", row_index=1,
        raw_values={"2theta": "14.1", "intensity": "1000"}
    )
    findings = run_materials_characterization_check([row_xrd])
    assert len(findings) == 1
    assert findings[0].risk_level == "low"
    assert "radiation source (e.g. Cu Ka)" in findings[0].observed_values["missing_metadata"]

    # XPS table missing calibration
    row_xps = PVMetricRow(
        row_id="3", source_file="xps_peaks.csv", table_id="tbl-3", row_index=1,
        raw_values={"binding_energy": "284.8"}
    )
    findings = run_materials_characterization_check([row_xps])
    assert len(findings) == 1
    assert any("calibration reference" in item for item in findings[0].observed_values["missing_metadata"])

    # PL table missing excitation wavelength
    row_pl = PVMetricRow(
        row_id="4", source_file="pl_spectrum.csv", table_id="tbl-4", row_index=1,
        raw_values={"pl_wavelength": "780"}
    )
    findings = run_materials_characterization_check([row_pl])
    assert len(findings) == 1
    assert any("excitation wavelength" in item for item in findings[0].observed_values["missing_metadata"])


def test_materials_characterization_requires_explicit_tokens_not_bare_substrings():
    # "sample" contains "pl" and "temperature" contains "tem", but neither
    # is an explicit materials-characterization token.
    row_false_positive = PVMetricRow(
        row_id="5", source_file="sample_metrics.csv", table_id="tbl-5", row_index=1,
        raw_values={"Temperature (C)": "25"},
    )
    assert run_materials_characterization_check([row_false_positive]) == []

    # A filename can provide candidate context but cannot create a finding alone.
    row_filename_only = PVMetricRow(
        row_id="6", source_file="xrd_results.csv", table_id="tbl-6", row_index=1,
        raw_values={"Value": "1"},
    )
    assert run_materials_characterization_check([row_filename_only]) == []


def test_materials_characterization_routes_explicit_aliases():
    cases = [
        ("XRD", "XRD"),
        ("XPS", "XPS"),
        ("TRPL", "PL/TRPL"),
        ("SEM image", "SEM/TEM"),
        ("TEM micrograph", "SEM/TEM"),
    ]
    for index, (header, expected_kind) in enumerate(cases, start=1):
        row = PVMetricRow(
            row_id=f"alias-{index}",
            source_file="metrics.csv",
            table_id=f"tbl-alias-{index}",
            row_index=1,
            raw_values={header: "present"},
        )
        findings = run_materials_characterization_check([row])
        assert len(findings) == 1, header
        assert findings[0].observed_values["characterization_type"] == expected_kind
