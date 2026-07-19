from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from openpyxl import Workbook

from integrity_agent.core.curves import (
    CurveColumnMapping,
    CurveReconciliationSpec,
    CurveSegmentSimilarityOptions,
    CurveTableSpec,
)
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.registry import run_detector
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi
from integrity_agent.core.safety import find_runtime_safety_issues
from integrity_agent.workflows.curve_reconciliation import (
    CurveReconciliationError,
    reconcile_curve_segment_similarity,
)
from integrity_agent.workflows.review_package import run_review_package
from integrity_agent.workflows.validate_ledger import validate_ledger_file


SEGMENT = [0.0, 1.7, -0.4, 3.9, 1.2, 5.6, -1.8, 4.4, 0.7, 6.3]


def _write_curve(path: Path, values: list[float]) -> Path:
    path.write_text(
        "time_s,signal\n"
        + "".join(f"{index},{value}\n" for index, value in enumerate(values)),
        encoding="utf-8",
    )
    return path


def _write_curve_rows(
    path: Path,
    rows: list[tuple[float, float]],
) -> Path:
    path.write_text(
        "time_s,signal\n"
        + "".join(f"{x},{value}\n" for x, value in rows),
        encoding="utf-8",
    )
    return path


def _table(path: Path, *, label: str, sample_id: str) -> CurveTableSpec:
    return CurveTableSpec(
        path=path,
        source_label=label,
        location=f"{label} rows 2 onward",
        sample_id=sample_id,
        source_version="publisher-v1",
    )


def _spec(
    first_path: Path,
    second_path: Path,
    *,
    minimum_window_points: int = 8,
) -> CurveReconciliationSpec:
    return CurveReconciliationSpec(
        source_table=_table(
            first_path,
            label=f"tables/{first_path.name}",
            sample_id="sample-A",
        ),
        plot_table=_table(
            second_path,
            label=f"tables/{second_path.name}",
            sample_id="sample-B",
        ),
        mapping=CurveColumnMapping(
            source_x="time_s",
            source_y="signal",
            plot_x="time_s",
            plot_y="signal",
            x_axis_kind="time",
        ),
        segment_similarity=CurveSegmentSimilarityOptions(
            human_confirmed_independent_curves=True,
            minimum_window_points=minimum_window_points,
        ),
    )


def _matching_paths(tmp_path: Path) -> tuple[Path, Path]:
    first = _write_curve(
        tmp_path / "first.csv",
        [2.3, -1.1, 4.7, *SEGMENT, 0.2, 8.1],
    )
    second = _write_curve(
        tmp_path / "second.csv",
        [9.2, -4.3, 1.1, 7.2, *[10.0 + 2.5 * value for value in SEGMENT], -8.0, 13.0],
    )
    return first, second


def _write_curve_xlsx(path: Path, values: list[float]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Curve"
    sheet.append(["time_s", "signal"])
    for index, value in enumerate(values):
        sheet.append([index, value])
    workbook.save(path)
    return path


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _status(summary, module_name: str) -> dict:
    return next(
        item.to_dict()
        for item in summary.module_statuses
        if item.module_name == module_name
    )


def test_nontrivial_affine_segment_match_is_medium_manual_candidate(tmp_path: Path):
    first, second = _matching_paths(tmp_path)

    findings = reconcile_curve_segment_similarity(_spec(first, second))

    assert len(findings) == 1
    record = findings[0].to_ledger_record()
    assert record["rule_id"] == "curve_segment_shape_similarity"
    assert record["risk_level"] == "medium"
    assert record["needs_manual_review"] is True
    assert record["manual_verification"]["needed"] is True
    assert "candidate segment-shape similarity" in record["safe_report_language"].lower()
    assert record["provenance"]["window_length"] == len(SEGMENT)
    assert record["provenance"]["transform"]["scale"] == pytest.approx(2.5)
    assert record["provenance"]["transform"]["offset"] == pytest.approx(10.0)
    assert record["provenance"]["similarity_metrics"]["absolute_correlation"] == pytest.approx(1.0)
    assert record["provenance"]["similarity_metrics"]["normalized_rmse"] <= 1e-12
    assert record["provenance"]["human_confirmed_independent_curves"] is True
    assert len(record["evidence"]) == 2
    assert record["evidence"][0]["source"] == "tables/first.csv"
    assert record["evidence"][1]["source"] == "tables/second.csv"
    assert "rows 5-14" in record["evidence"][0]["location"]
    assert "rows 6-15" in record["evidence"][1]["location"]
    for item in record["evidence"]:
        assert item["metadata"]["source_hash"].startswith("sha256:")
        assert "row_start" in item["metadata"]
        assert "row_end" in item["metadata"]
    assert str(tmp_path.resolve()) not in json.dumps(record)

    ledger = tmp_path / "segment_findings.jsonl"
    ledger.write_text(findings[0].to_json_line() + "\n", encoding="utf-8")
    assert validate_ledger_file(ledger).ok


def test_supplied_xlsx_curves_use_the_same_explicit_numeric_contract(tmp_path: Path):
    first = _write_curve_xlsx(
        tmp_path / "first.xlsx",
        [2.3, -1.1, 4.7, *SEGMENT, 0.2, 8.1],
    )
    second = _write_curve_xlsx(
        tmp_path / "second.xlsx",
        [9.2, -4.3, 1.1, 7.2, *[10.0 + 2.5 * value for value in SEGMENT], -8.0, 13.0],
    )
    spec = _spec(first, second)
    spec.source_table.sheet_name = "Curve"
    spec.plot_table.sheet_name = "Curve"

    findings = reconcile_curve_segment_similarity(spec)

    assert len(findings) == 1
    assert findings[0].provenance["window_length"] == len(SEGMENT)
    assert all(
        item.metadata["source_hash"].startswith("sha256:")
        for item in findings[0].evidence
    )


@pytest.mark.parametrize(
    "first_values,second_values,minimum_window_points",
    [
        ([4.0] * 12, [9.0] * 12, 8),
        ([float(index) for index in range(12)], [5.0 + 2.0 * index for index in range(12)], 8),
        (
            [1000.0 + value * 1e-6 for value in SEGMENT],
            [2000.0 + value * 2e-6 for value in SEGMENT],
            8,
        ),
        (SEGMENT[:7], [10.0 + 2.5 * value for value in SEGMENT[:7]], 8),
    ],
)
def test_constant_linear_low_dynamic_range_and_short_series_are_ignored(
    tmp_path: Path,
    first_values: list[float],
    second_values: list[float],
    minimum_window_points: int,
):
    first = _write_curve(tmp_path / "first.csv", first_values)
    second = _write_curve(tmp_path / "second.csv", second_values)

    assert reconcile_curve_segment_similarity(
        _spec(first, second, minimum_window_points=minimum_window_points)
    ) == []


def test_overlapping_windows_of_the_same_curve_are_ignored(tmp_path: Path):
    curve = _write_curve(tmp_path / "same.csv", SEGMENT)
    spec = _spec(curve, curve)
    spec.plot_table.source_label = "tables/same.csv"
    spec.plot_table.sample_id = "sample-A"

    assert reconcile_curve_segment_similarity(spec) == []


def test_missing_rows_do_not_bridge_two_fragments_into_one_contiguous_match(
    tmp_path: Path,
):
    first = _write_curve(
        tmp_path / "first.csv",
        [*SEGMENT[:4], float("nan"), *SEGMENT[4:]],
    )
    second = _write_curve(
        tmp_path / "second.csv",
        [10.0 + 2.5 * value for value in SEGMENT],
    )

    assert reconcile_curve_segment_similarity(_spec(first, second)) == []


def test_blank_csv_row_is_a_real_gap_and_preserves_source_row_numbers(
    tmp_path: Path,
):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text(
        "time_s,signal\n"
        "0,99\n1,-88\n2,77\n3,-66\n\n"
        + "".join(
            f"{index + 4},{value}\n" for index, value in enumerate(SEGMENT)
        ),
        encoding="utf-8",
    )
    second.write_text(
        "time_s,signal\n"
        "0,-3\n1,12\n2,0\n3,9\n\n"
        + "".join(
            f"{index + 4},{10 + 2.5 * value}\n"
            for index, value in enumerate(SEGMENT)
        ),
        encoding="utf-8",
    )

    finding = reconcile_curve_segment_similarity(_spec(first, second))[0]

    assert finding.provenance["window_length"] == len(SEGMENT)
    assert finding.provenance["first_segment"]["row_start"] == 7
    assert finding.provenance["second_segment"]["row_start"] == 7


def test_blank_xlsx_row_is_a_real_gap_and_preserves_source_row_numbers(
    tmp_path: Path,
):
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    for path, prelude, transform in (
        (first, [99, -88, 77, -66], lambda value: value),
        (second, [-3, 12, 0, 9], lambda value: 10 + 2.5 * value),
    ):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Curve"
        sheet.append(["time_s", "signal"])
        for index, value in enumerate(prelude):
            sheet.append([index, value])
        sheet.append([None, None])
        for index, value in enumerate(SEGMENT):
            sheet.append([index + 4, transform(value)])
        workbook.save(path)

    spec = _spec(first, second)
    spec.source_table.sheet_name = "Curve"
    spec.plot_table.sheet_name = "Curve"
    finding = reconcile_curve_segment_similarity(spec)[0]

    assert finding.provenance["window_length"] == len(SEGMENT)
    assert finding.provenance["first_segment"]["row_start"] == 7
    assert finding.provenance["second_segment"]["row_start"] == 7


def test_nonuniform_x_axis_linear_curves_are_not_shape_candidates(tmp_path: Path):
    first_x = [0, 1, 2, 4, 7, 11, 16, 22, 29, 37]
    second_x = [2 * value + 5 for value in first_x]
    first = _write_curve_rows(
        tmp_path / "first.csv",
        [(x, 3 * x + 1) for x in first_x],
    )
    second = _write_curve_rows(
        tmp_path / "second.csv",
        [(x, 3 * x + 1) for x in second_x],
    )

    assert reconcile_curve_segment_similarity(_spec(first, second)) == []


def test_axis_inverted_signal_is_not_a_medium_scoring_candidate(tmp_path: Path):
    first = _write_curve(tmp_path / "first.csv", SEGMENT)
    second = _write_curve(
        tmp_path / "second.csv",
        [10.0 - 2.5 * value for value in SEGMENT],
    )

    assert reconcile_curve_segment_similarity(_spec(first, second)) == []


def test_longer_valid_match_is_recovered_when_minimum_prefix_is_linear(
    tmp_path: Path,
):
    values = [float(index) for index in range(8)] + [20.0, -5.0]
    first = _write_curve(tmp_path / "first.csv", values)
    second = _write_curve(
        tmp_path / "second.csv",
        [7.0 + 1.5 * value for value in values],
    )

    findings = reconcile_curve_segment_similarity(_spec(first, second))

    assert len(findings) == 1
    assert findings[0].provenance["window_length"] == len(values)


def test_curve_search_fails_explicitly_when_input_exceeds_declared_budget(
    tmp_path: Path,
):
    first = _write_curve(tmp_path / "first.csv", SEGMENT)
    second = _write_curve(tmp_path / "second.csv", SEGMENT)
    spec = _spec(first, second)
    spec.segment_similarity.maximum_points_per_curve = 8

    with pytest.raises(CurveReconciliationError, match="maximum_points_per_curve"):
        reconcile_curve_segment_similarity(spec)


def test_xlsx_uses_first_worksheet_when_sheet_name_is_not_supplied(tmp_path: Path):
    first = _write_curve_xlsx(tmp_path / "first.xlsx", SEGMENT)
    second = _write_curve_xlsx(
        tmp_path / "second.xlsx",
        [10.0 + 2.5 * value for value in SEGMENT],
    )
    spec = _spec(first, second)
    spec.source_table.sheet_name = None
    spec.plot_table.sheet_name = None

    findings = reconcile_curve_segment_similarity(spec)

    assert len(findings) == 1


def test_same_xlsx_series_is_recognized_with_default_and_explicit_sheet_names(
    tmp_path: Path,
):
    curve = _write_curve_xlsx(tmp_path / "same.xlsx", SEGMENT)
    spec = _spec(curve, curve)
    spec.source_table.sheet_name = None
    spec.plot_table.sheet_name = "Curve"

    assert reconcile_curve_segment_similarity(spec) == []


def test_same_csv_series_is_recognized_with_case_insensitive_column_aliases(
    tmp_path: Path,
):
    curve = _write_curve(tmp_path / "same.csv", SEGMENT)
    spec = _spec(curve, curve)
    spec.mapping.plot_x = "TIME_S"
    spec.mapping.plot_y = "Signal"

    assert reconcile_curve_segment_similarity(spec) == []


def test_same_csv_series_with_repeated_nonoverlapping_fragments_is_not_compared(
    tmp_path: Path,
):
    repeated = _write_curve(
        tmp_path / "same.csv",
        [*SEGMENT, float("nan"), *SEGMENT],
    )
    spec = _spec(repeated, repeated)
    spec.mapping.plot_x = "TIME_S"
    spec.mapping.plot_y = "Signal"

    assert reconcile_curve_segment_similarity(spec) == []


def test_same_xlsx_series_with_repeated_nonoverlapping_fragments_is_not_compared(
    tmp_path: Path,
):
    repeated = _write_curve_xlsx(
        tmp_path / "same.xlsx",
        [*SEGMENT, float("nan"), *SEGMENT],
    )
    spec = _spec(repeated, repeated)
    spec.source_table.sheet_name = None
    spec.plot_table.sheet_name = "Curve"

    assert reconcile_curve_segment_similarity(spec) == []


def test_finding_identity_includes_column_mapping_and_file_hashes(tmp_path: Path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text(
        "time_s,signal_a,signal_b\n"
        + "".join(
            f"{index},{value},{value + (index % 3) * 0.37}\n"
            for index, value in enumerate(SEGMENT)
        ),
        encoding="utf-8",
    )
    second.write_text(
        "time_s,signal_a,signal_b\n"
        + "".join(
            f"{index},{10 + 2.5 * value},{20 + 1.7 * (value + (index % 3) * 0.37)}\n"
            for index, value in enumerate(SEGMENT)
        ),
        encoding="utf-8",
    )
    first_spec = _spec(first, second)
    first_spec.mapping.source_y = "signal_a"
    first_spec.mapping.plot_y = "signal_a"
    second_spec = _spec(first, second)
    second_spec.mapping.source_y = "signal_b"
    second_spec.mapping.plot_y = "signal_b"

    first_finding = reconcile_curve_segment_similarity(first_spec)[0]
    second_finding = reconcile_curve_segment_similarity(second_spec)[0]

    assert first_finding.finding_id != second_finding.finding_id
    assert (
        first_finding.provenance["correlation_group"]
        == second_finding.provenance["correlation_group"]
    )


def test_segment_similarity_requires_explicit_mapping_and_human_confirmation(
    tmp_path: Path,
):
    first, second = _matching_paths(tmp_path)
    with pytest.raises(ValueError, match="explicit curve column mapping"):
        CurveReconciliationSpec(
            source_table=_table(first, label="tables/first.csv", sample_id="sample-A"),
            plot_table=_table(second, label="tables/second.csv", sample_id="sample-B"),
            mapping=None,
            segment_similarity=CurveSegmentSimilarityOptions(
                human_confirmed_independent_curves=True,
            ),
        )

    with pytest.raises(ValueError, match="human-confirmed independent curves"):
        CurveSegmentSimilarityOptions(human_confirmed_independent_curves=False)


def test_active_rule_adapter_matches_runtime_contract(tmp_path: Path):
    first, second = _matching_paths(tmp_path)
    project_root = Path(__file__).resolve().parents[1]
    rule = load_rule_registry(project_root / "knowledge_base" / "detector_rules")[
        "curve_segment_shape_similarity"
    ]

    records = run_detector(
        rule,
        project_root,
        options={"spec": _spec(first, second)},
    )

    assert rule.runtime_status == "active"
    assert rule.execution_mode == "offline"
    assert rule.risk_ceiling == "medium"
    assert len(records) == 1
    assert records[0].risk_level == "medium"
    assert records[0].metadata["needs_manual_review"] is True


def test_review_package_writes_segment_child_ledger_status_and_unified_record(
    tmp_path: Path,
):
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    tables_dir = package_dir / "tables"
    documents_dir.mkdir(parents=True)
    tables_dir.mkdir()
    first, second = _matching_paths(tables_dir)

    (documents_dir / "curve_reconciliations.yml").write_text(
        yaml.safe_dump(
            {
                "reconciliations": [
                    {
                        "source_table": {
                            "path": f"tables/{first.name}",
                            "location": "first source rows 2 onward",
                            "sample_id": "sample-A",
                            "source_version": "publisher-v1",
                        },
                        "plot_table": {
                            "path": f"tables/{second.name}",
                            "location": "second source rows 2 onward",
                            "sample_id": "sample-B",
                            "source_version": "publisher-v1",
                        },
                        "mapping": {
                            "source_x": "time_s",
                            "source_y": "signal",
                            "plot_x": "time_s",
                            "plot_y": "signal",
                            "x_axis_kind": "time",
                        },
                        "segment_similarity": {
                            "human_confirmed_independent_curves": True,
                            "minimum_window_points": 8,
                        },
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    child_ledger = output_dir / "curve_reconciliation" / "curve_segment_similarity.jsonl"
    unified_ledger = output_dir / "unified_evidence_index.jsonl"
    assert child_ledger.exists()
    assert validate_ledger_file(child_ledger).ok
    assert validate_ledger_file(unified_ledger).ok
    child_records = _records(child_ledger)
    assert len(child_records) == 1
    assert child_records[0]["rule_id"] == "curve_segment_shape_similarity"
    assert any(
        record.get("rule_id") == "curve_segment_shape_similarity"
        for record in _records(unified_ledger)
    )
    status = _status(summary, "curve-segment-similarity")
    assert status["status"] == "success"
    assert status["input_artifact_count"] == 1
    assert status["parsed_row_count"] == 1
    assert status["finding_count"] == 1
    assert str(package_dir.resolve()) not in child_ledger.read_text(encoding="utf-8")


def test_review_package_runs_point_coverage_and_segment_checks_for_same_spec(
    tmp_path: Path,
):
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    tables_dir = package_dir / "tables"
    documents_dir.mkdir(parents=True)
    tables_dir.mkdir()
    source_values = [*SEGMENT, 2.2, -3.1, 7.7]
    source = _write_curve_rows(
        tables_dir / "source.csv",
        [(index, value) for index, value in enumerate(source_values)],
    )
    plot = _write_curve_rows(
        tables_dir / "plot.csv",
        [
            (index, 10.0 + 2.5 * value)
            for index, value in enumerate(source_values)
            if index not in {8, 9}
        ],
    )
    payload = {
        "reconciliations": [
            {
                "source_table": {
                    "path": f"tables/{source.name}",
                    "location": "source rows",
                    "sample_id": "sample-A",
                    "source_version": "publisher-v1",
                },
                "plot_table": {
                    "path": f"tables/{plot.name}",
                    "location": "plot rows",
                    "sample_id": "sample-A",
                    "source_version": "publisher-v1",
                },
                "mapping": {
                    "source_x": "time_s",
                    "source_y": "signal",
                    "plot_x": "time_s",
                    "plot_y": "signal",
                    "x_axis_kind": "time",
                },
                "segment_similarity": {
                    "human_confirmed_independent_curves": True,
                    "minimum_window_points": 8,
                },
            }
        ]
    }
    (documents_dir / "curve_reconciliations.yml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )
    rules = {
        record["rule_id"]
        for record in _records(output_dir / "unified_evidence_index.jsonl")
    }

    assert "curve_point_coverage" in rules
    assert "curve_segment_shape_similarity" in rules
    assert _status(summary, "curve-point-coverage")["parsed_row_count"] == 1
    assert _status(summary, "curve-segment-similarity")["parsed_row_count"] == 1


def test_review_package_marks_empty_curve_input_as_warning(tmp_path: Path):
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "curve_reconciliations.yml").write_text(
        "reconciliations: []\n",
        encoding="utf-8",
    )

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(tmp_path / "output"),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    for module_name in ("curve-point-coverage", "curve-segment-similarity"):
        status = _status(summary, module_name)
        assert status["status"] == "warning"
        assert status["parsed_row_count"] == 0
        assert status["skip_reason"] == "no_parsed_records"


def test_curve_failure_status_and_manifest_redact_runtime_absolute_paths(
    tmp_path: Path,
):
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    documents_dir.mkdir(parents=True)
    payload = {
        "reconciliations": [
            {
                "source_table": {
                    "path": "tables/source.txt",
                    "location": "source rows",
                    "sample_id": "sample-A",
                    "source_version": "publisher-v1",
                },
                "plot_table": {
                    "path": "tables/plot.txt",
                    "location": "plot rows",
                    "sample_id": "sample-B",
                    "source_version": "publisher-v1",
                },
                "mapping": {
                    "source_x": "time_s",
                    "source_y": "signal",
                    "plot_x": "time_s",
                    "plot_y": "signal",
                    "x_axis_kind": "time",
                },
                "segment_similarity": {
                    "human_confirmed_independent_curves": True,
                },
            }
        ]
    }
    (documents_dir / "curve_reconciliations.yml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    status_records = _records(output_dir / "module_status.jsonl")
    manifest = json.loads(
        (output_dir / "review_package_manifest.json").read_text(encoding="utf-8")
    )
    public_payload = {"manifest": manifest, "statuses": status_records}
    serialized = json.dumps(public_payload, ensure_ascii=False)
    assert _status(summary, "curve-segment-similarity")["status"] == "failed"
    assert find_runtime_safety_issues(public_payload) == []
    assert str(package_dir.resolve()) not in serialized
    assert str(output_dir.resolve()) not in serialized
    assert "<local-path>" in serialized


def test_reversed_curve_pair_has_stable_identity_and_scores_once(tmp_path: Path):
    first, second = _matching_paths(tmp_path)
    forward = reconcile_curve_segment_similarity(_spec(first, second))[0]
    reverse = reconcile_curve_segment_similarity(_spec(second, first))[0]

    assert forward.finding_id == reverse.finding_id
    assert (
        forward.provenance["correlation_group"]
        == reverse.provenance["correlation_group"]
    )
    assert calculate_mrpi([forward, reverse]) == 15.0


def test_reversed_pair_uses_direction_independent_tie_break_for_equal_matches(
    tmp_path: Path,
):
    first_segment = [0, 3, -2, 5, 1, 7, -4, 6, 2, 8]
    second_segment = [4, -1, 6, -3, 9, 2, 7, -5, 8, 1]
    first = _write_curve(
        tmp_path / "a.csv",
        [*first_segment, float("nan"), *second_segment],
    )
    second = _write_curve(
        tmp_path / "b.csv",
        [
            *[10 + 2 * value for value in second_segment],
            float("nan"),
            *[10 + 2 * value for value in first_segment],
        ],
    )

    forward = reconcile_curve_segment_similarity(_spec(first, second))[0]
    reverse = reconcile_curve_segment_similarity(_spec(second, first))[0]

    assert forward.finding_id == reverse.finding_id
    assert (
        forward.provenance["correlation_group"]
        == reverse.provenance["correlation_group"]
    )
