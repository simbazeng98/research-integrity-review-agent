from __future__ import annotations

import json

from integrity_agent.domains.photovoltaics.field_mapping import infer_pv_field_mapping
from integrity_agent.domains.photovoltaics.pce_consistency import run_pce_consistency_check
from integrity_agent.domains.photovoltaics.schema import PVMetricRow, build_pv_metric_rows
from integrity_agent.domains.photovoltaics.stability_reporting import run_pv_stability_reporting_check


def _write_manifest(path, csv_path, columns):
    path.write_text(
        json.dumps(
            {
                "table_id": "tbl-001",
                "source_file": csv_path.name,
                "relative_path": str(csv_path),
                "source_format": "csv",
                "sheet_name": None,
                "row_count": 1,
                "column_count": len(columns),
                "columns": columns,
                "warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_pv_measurement_context_headers_map_to_distinct_canonical_fields():
    expected = {
        "Light intensity (mW/cm2)": "light_intensity_mw_cm2",
        "Stability duration (h)": "stability_duration_h",
        "Stabilized power output (%)": "stabilized_power_output_percent",
    }

    for header, canonical_field in expected.items():
        mapping = infer_pv_field_mapping(header)
        assert mapping is not None, header
        assert mapping.canonical_field == canonical_field


def test_non_standard_illumination_and_empty_environment_cells_keep_context_distinct(tmp_path):
    columns = [
        "Device ID",
        "Voc (V)",
        "Jsc (mA/cm2)",
        "FF (%)",
        "PCE (%)",
        "Light intensity (mW/cm2)",
        "Stability duration (h)",
        "Stabilized power output (%)",
        "Temperature (C)",
        "Humidity (%)",
        "MPP tracking",
        "Encapsulation",
    ]
    csv_path = tmp_path / "pv_metrics.csv"
    csv_path.write_text(
        ",".join(columns)
        + "\n"
        + "device-1,1.10,22.0,75.0,22.6875,80,500,21.0,,,on,glass\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(manifest_path, csv_path, columns)

    rows = build_pv_metric_rows(manifest_path)
    assert len(rows) == 1
    row = rows[0]
    assert row.light_intensity_mw_cm2 == 80.0
    assert row.stability_duration_h == 500.0
    assert row.t80_h is None
    assert row.stabilized_power_output_percent == 21.0
    assert row.stabilized_pce_percent is None

    assert not run_pce_consistency_check(rows)

    stability_findings = run_pv_stability_reporting_check(rows)
    assert len(stability_findings) == 1
    missing_conditions = stability_findings[0].observed_values["missing_conditions"]
    assert "temperature conditions" in missing_conditions
    assert "humidity or atmospheric environment" in missing_conditions


def test_unparsable_reported_illumination_produces_low_risk_context_finding_not_one_sun_recalculation():
    row = PVMetricRow(
        row_id="tbl-001-row-1",
        source_file="pv_metrics.csv",
        table_id="tbl-001",
        row_index=1,
        voc_v=1.10,
        jsc_ma_cm2=22.0,
        ff=0.75,
        pce_percent=22.6875,
        raw_values={"Light intensity (mW/cm2)": "calibration-pending"},
        warnings=["Could not parse light intensity value as numeric"],
    )

    findings = run_pce_consistency_check([row])

    assert len(findings) == 1
    assert findings[0].rule_id == "pv_pce_missing_illumination_context"
    assert findings[0].risk_level == "low"
    assert "could not be parsed" in findings[0].safe_report_language.lower()
    assert all(finding.rule_id != "pv_pce_consistency" for finding in findings)
