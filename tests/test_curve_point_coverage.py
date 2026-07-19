from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from integrity_agent.core.curves import (
    CurveColumnMapping,
    CurveDisclosure,
    CurveInterval,
    CurveReconciliationSpec,
    CurveTableSpec,
)
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.registry import run_detector
from integrity_agent.workflows.curve_reconciliation import (
    reconcile_curve_coverage,
    run_curve_reconciliation,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _write_csv(path: Path, rows: list[tuple[object, object]]) -> Path:
    path.write_text(
        "voltage,current\n"
        + "".join(f"{x},{y}\n" for x, y in rows),
        encoding="utf-8",
    )
    return path


def _table(path: Path, *, kind: str) -> CurveTableSpec:
    return CurveTableSpec(
        path=path,
        source_label=f"tables/{path.name}",
        location=f"{kind} sheet rows 2 onward",
        sample_id="device-A",
        source_version="publisher-v1",
    )


def _spec(
    source_path: Path,
    plot_path: Path,
    *,
    mapping: CurveColumnMapping | None = None,
    disclosure: CurveDisclosure | None = None,
) -> CurveReconciliationSpec:
    return CurveReconciliationSpec(
        source_table=_table(source_path, kind="source-data"),
        plot_table=_table(plot_path, kind="plot-data"),
        mapping=mapping
        if mapping is not None
        else CurveColumnMapping(
            source_x="voltage",
            source_y="current",
            plot_x="voltage",
            plot_y="current",
            x_axis_kind="voltage",
        ),
        disclosure=disclosure or CurveDisclosure(),
    )


def test_curve_table_schema_accepts_csv_xlsx_but_rejects_image_digitization(
    tmp_path: Path,
):
    csv_path = tmp_path / "source.csv"
    csv_path.touch()
    xlsx_path = tmp_path / "plot.xlsx"
    xlsx_path.touch()

    assert _table(csv_path, kind="source").path.suffix == ".csv"
    assert _table(xlsx_path, kind="plot").path.suffix == ".xlsx"

    with pytest.raises(ValidationError, match="CSV/XLSX"):
        _table(tmp_path / "figure.png", kind="plot")


def test_disclosed_downsampled_curve_does_not_trigger(tmp_path: Path):
    source = _write_csv(
        tmp_path / "source.csv",
        [(index, index * 2) for index in range(11)],
    )
    plot = _write_csv(
        tmp_path / "plot.csv",
        [(index, index * 2) for index in range(0, 11, 2)],
    )
    spec = _spec(
        source,
        plot,
        disclosure=CurveDisclosure(
            downsampling_disclosed=True,
            downsample_factor=2,
        ),
    )

    assert reconcile_curve_coverage(spec) == []


def test_unexplained_contiguous_internal_interval_is_low_non_scoring_question(
    tmp_path: Path,
):
    source = _write_csv(
        tmp_path / "source.csv",
        [(index, index * 2) for index in range(11)],
    )
    plot = _write_csv(
        tmp_path / "plot.csv",
        [(index, index * 2) for index in [0, 1, 2, 6, 7, 8, 9, 10]],
    )

    findings = reconcile_curve_coverage(_spec(source, plot))

    assert len(findings) == 1
    record = findings[0].to_ledger_record()
    assert record["risk_level"] == "low"
    assert record["type"] == "curve_point_coverage_question"
    assert record["provenance"]["open_for_scoring"] is False
    assert record["provenance"]["mrpi_eligible"] is False
    assert record["provenance"]["comparison_kind"] == "unexplained_contiguous_missing_interval"
    assert record["provenance"]["missing_intervals"] == [
        {"x_start": "3", "x_end": "5", "point_count": 3}
    ]
    assert len(record["evidence"]) == 2
    for item in record["evidence"]:
        metadata = item["metadata"]
        assert metadata["source_hash"].startswith("sha256:")
        assert metadata["sample_id"] == "device-A"
        assert metadata["source_version"] == "publisher-v1"
        assert item["location"]
    serialized = json.dumps(record).lower()
    assert "deleted data" not in serialized
    assert "candidate" in str(record["safe_report_language"]).lower()


def test_axis_clipping_source_nans_and_disclosed_filtering_are_distinguished(
    tmp_path: Path,
):
    source = _write_csv(
        tmp_path / "source.csv",
        [(index, index * 2) for index in range(11)],
    )
    clipped_plot = _write_csv(
        tmp_path / "clipped.csv",
        [(index, index * 2) for index in range(2, 9)],
    )
    assert reconcile_curve_coverage(
        _spec(
            source,
            clipped_plot,
            disclosure=CurveDisclosure(axis_limits=(2, 8)),
        )
    ) == []

    nan_source = _write_csv(
        tmp_path / "source_nan.csv",
        [(index, "NaN" if index in {4, 5} else index * 2) for index in range(11)],
    )
    nan_plot = _write_csv(
        tmp_path / "plot_nan.csv",
        [(index, index * 2) for index in range(11) if index not in {4, 5}],
    )
    assert reconcile_curve_coverage(_spec(nan_source, nan_plot)) == []

    filtered_plot = _write_csv(
        tmp_path / "filtered.csv",
        [(index, index * 2) for index in range(11) if index not in {3, 4, 5}],
    )
    assert reconcile_curve_coverage(
        _spec(
            source,
            filtered_plot,
            disclosure=CurveDisclosure(
                filtering_disclosed=True,
                filtered_intervals=[CurveInterval(start=3, end=5)],
            ),
        )
    ) == []


def test_generic_filter_disclosure_without_intervals_is_context_question(
    tmp_path: Path,
):
    source = _write_csv(
        tmp_path / "source.csv",
        [(index, index * 2) for index in range(11)],
    )
    plot = _write_csv(
        tmp_path / "plot.csv",
        [(index, index * 2) for index in range(11) if index not in {3, 4, 5}],
    )

    findings = reconcile_curve_coverage(
        _spec(
            source,
            plot,
            disclosure=CurveDisclosure(filtering_disclosed=True),
        )
    )

    assert len(findings) == 1
    assert findings[0].provenance["comparison_kind"] == (
        "filtering_disclosed_without_intervals"
    )
    assert findings[0].provenance["open_for_scoring"] is False


def test_supplied_curve_hash_must_match_the_table(tmp_path: Path):
    source = _write_csv(tmp_path / "source.csv", [(0, 0), (1, 2), (2, 4)])
    plot = _write_csv(tmp_path / "plot.csv", [(0, 0), (2, 4)])
    spec = _spec(source, plot)
    spec.mapping = None
    spec.source_table.source_hash = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="hash"):
        reconcile_curve_coverage(spec)


def test_disclosed_smoothing_with_full_x_coverage_does_not_trigger(tmp_path: Path):
    source = _write_csv(
        tmp_path / "source.csv",
        [(index, index * 2) for index in range(11)],
    )
    smoothed_plot = _write_csv(
        tmp_path / "smoothed.csv",
        [(index, index * 2 + 0.25) for index in range(11)],
    )

    assert reconcile_curve_coverage(
        _spec(
            source,
            smoothed_plot,
            disclosure=CurveDisclosure(smoothing_disclosed=True),
        )
    ) == []


def test_missing_source_mapping_is_context_only_and_never_claims_omission(
    tmp_path: Path,
):
    source = _write_csv(tmp_path / "source.csv", [(0, 0), (1, 2), (2, 4)])
    plot = _write_csv(tmp_path / "plot.csv", [(0, 0), (2, 4)])
    spec = CurveReconciliationSpec(
        source_table=_table(source, kind="source-data"),
        plot_table=_table(plot, kind="plot-data"),
        mapping=None,
    )

    findings = reconcile_curve_coverage(spec)

    assert len(findings) == 1
    record = findings[0].to_ledger_record()
    assert record["risk_level"] == "low"
    assert record["provenance"]["comparison_kind"] == "missing_source_mapping"
    assert record["provenance"]["open_for_scoring"] is False
    assert "deleted data" not in json.dumps(record).lower()


def test_xlsx_tables_are_reconciled_without_image_digitization(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    plot = tmp_path / "plot.xlsx"
    for path, indices in ((source, range(8)), (plot, [0, 1, 5, 6, 7])):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Data"
        sheet.append(["voltage", "current"])
        for index in indices:
            sheet.append([index, index * 2])
        workbook.save(path)

    spec = _spec(source, plot)
    spec.source_table.sheet_name = "Data"
    spec.plot_table.sheet_name = "Data"
    findings = reconcile_curve_coverage(spec)

    assert len(findings) == 1
    assert findings[0].provenance["missing_intervals"] == [
        {"x_start": "2", "x_end": "4", "point_count": 3}
    ]
    assert "image" not in findings[0].provenance["comparison_mode"]


def test_workflow_rule_adapter_and_ledger_validation(tmp_path: Path):
    source = _write_csv(
        tmp_path / "source.csv",
        [(index, index * 2) for index in range(8)],
    )
    plot = _write_csv(
        tmp_path / "plot.csv",
        [(index, index * 2) for index in [0, 1, 5, 6, 7]],
    )
    spec = _spec(source, plot)

    ledger_path, summary_path = run_curve_reconciliation(
        spec,
        output_dir=tmp_path / "review",
    )
    validation = validate_ledger_file(ledger_path)
    assert validation.ok, [issue.format() for issue in validation.issues]
    assert validation.records == 1
    assert summary_path.exists()

    project_root = Path(__file__).resolve().parents[1]
    rule = load_rule_registry(project_root / "knowledge_base" / "detector_rules")[
        "curve_point_coverage"
    ]
    records = run_detector(
        rule,
        project_root,
        options={"spec": spec},
    )
    assert len(records) == 1
    assert records[0].risk_level == "low"
    assert records[0].metadata["open_for_scoring"] is False
