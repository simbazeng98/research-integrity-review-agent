from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.core.tables.column_profiler import profile_column
from integrity_agent.core.tables.table_schema import ColumnProfile
from integrity_agent.detectors.numeric.quantization_grid import (
    analyze_quantization_grid,
    detect_quantization_grid,
)
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _rule():
    return load_rule_registry(
        _project_root() / "knowledge_base" / "detector_rules"
    )["measurement_precision_anomaly"]


def _quantized_values() -> list[str]:
    levels = ["0.100", "0.150", "0.200", "0.250", "0.300", "0.350", "0.400"]
    order = [0, 2, 1, 3, 3, 4, 2, 5, 1, 6, 4, 4, 3, 0, 2, 5] * 2
    return [levels[index] for index in order]


def _write_csv(path: Path, values: list[str]) -> None:
    path.write_text(
        "time_s,signal\n"
        + "".join(f"{index},{value}\n" for index, value in enumerate(values)),
        encoding="utf-8",
    )


def test_quantization_metrics_expose_full_audit_contract_and_profile_precision():
    values = _quantized_values()
    profile = profile_column("signal", values)

    metrics = analyze_quantization_grid(values, profile=profile)
    record = metrics.to_dict()

    assert metrics.total_count == 32
    assert metrics.unique_count == 7
    assert metrics.unique_ratio == pytest.approx(7 / 32)
    assert metrics.modal_value == pytest.approx(0.2)
    assert metrics.modal_count >= 4
    assert metrics.modal_ratio == pytest.approx(metrics.modal_count / 32)
    assert metrics.run_lengths
    assert metrics.max_run_length >= 2
    assert metrics.min_positive_step == pytest.approx(0.05)
    assert metrics.lattice_step == pytest.approx(0.05)
    assert metrics.lattice_residual <= 1e-9
    assert metrics.grid_overlap is None
    assert metrics.declared_resolution is None
    assert metrics.precision_hint == profile.precision_hint == 0.001
    for key in (
        "total_count",
        "unique_count",
        "unique_ratio",
        "modal_value",
        "modal_count",
        "modal_ratio",
        "run_lengths",
        "min_positive_step",
        "lattice_step",
        "lattice_residual",
        "grid_overlap",
        "declared_resolution",
    ):
        assert key in record


def test_continuous_series_does_not_create_a_candidate(tmp_path):
    values = [f"{math.sin(index * 0.73) + index * 0.013:.6f}" for index in range(36)]
    csv_path = tmp_path / "continuous.csv"
    _write_csv(csv_path, values)

    results = detect_quantization_grid(
        csv_path,
        _rule(),
        options={"file_path": csv_path, "value_column": "signal"},
    )

    assert results == []


def test_quantized_fixture_emits_medium_validator_clean_candidate(tmp_path):
    csv_path = (
        _project_root()
        / "examples"
        / "toy_table_package"
        / "toy_quantized_timeseries.csv"
    )
    values = _quantized_values()
    profile = profile_column("signal", values)

    results = detect_quantization_grid(
        csv_path,
        _rule(),
        options={
            "file_path": csv_path,
            "value_column": "signal",
            "profile": profile,
        },
    )

    assert len(results) == 1
    result = results[0]
    assert result.rule_id == "measurement_precision_anomaly"
    assert result.risk_level == "medium"
    assert "candidate" in result.safe_report_language.lower()
    assert result.metadata["runtime_status"] == "active"
    assert result.metadata["precision_hint"] == 0.001
    assert result.metadata["lattice_step"] == pytest.approx(0.05)
    assert result.metadata["declared_resolution"] is None
    assert result.metadata["resolution_explains_grid"] is False
    assert result.metadata["risk_ceiling"] == "medium"

    ledger_path = tmp_path / "quantization.jsonl"
    ledger_path.write_text(result.to_json_line() + "\n", encoding="utf-8")
    validation = validate_ledger_file(ledger_path)
    assert validation.ok, [issue.format() for issue in validation.issues]


def test_passed_column_profile_precision_can_suppress_formatting_grid(tmp_path):
    csv_path = tmp_path / "profile_resolution.csv"
    values = _quantized_values()
    _write_csv(csv_path, values)
    declared_profile = ColumnProfile(
        column_name="signal",
        inferred_type="float",
        numeric_count=len(values),
        missing_count=0,
        unique_count=len(set(values)),
        precision_hint=0.05,
    )

    results = detect_quantization_grid(
        csv_path,
        _rule(),
        options={
            "file_path": csv_path,
            "value_column": "signal",
            "profile": declared_profile,
        },
    )

    assert results == []


def test_declared_resolution_fixture_explains_and_suppresses_grid():
    csv_path = (
        _project_root()
        / "examples"
        / "toy_table_package"
        / "toy_declared_resolution_timeseries.csv"
    )

    results = detect_quantization_grid(
        csv_path,
        _rule(),
        options={"file_path": csv_path, "value_column": "signal"},
    )

    assert results == []


def test_declared_resolution_is_retained_in_metrics():
    metrics = analyze_quantization_grid(
        _quantized_values(),
        profile=profile_column("signal", _quantized_values()),
        declared_resolution="0.050",
    )

    assert metrics.declared_resolution == pytest.approx(0.05)
    assert metrics.resolution_explains_grid is True


def test_ordinary_rounding_at_reported_precision_is_not_elevated(tmp_path):
    values = [
        "0.1", "0.4", "0.9", "1.2", "1.8", "2.1", "2.7", "3.0",
        "3.6", "4.1", "4.8", "5.2", "5.9", "6.3", "6.8", "7.4",
        "7.9", "8.5", "9.0", "9.7", "10.1", "10.8", "11.3", "11.9",
    ]
    csv_path = tmp_path / "rounded.csv"
    _write_csv(csv_path, values)

    results = detect_quantization_grid(
        csv_path,
        _rule(),
        options={"file_path": csv_path, "value_column": "signal"},
    )

    assert results == []


def test_normalized_grid_is_never_medium(tmp_path):
    csv_path = tmp_path / "normalized.csv"
    _write_csv(csv_path, _quantized_values())

    results = detect_quantization_grid(
        csv_path,
        _rule(),
        options={
            "file_path": csv_path,
            "value_column": "signal",
            "normalized": True,
        },
    )

    assert all(result.risk_level == "low" for result in results)
    if results:
        assert results[0].metadata["normalization_declared"] is True


def test_small_sample_is_suppressed():
    values = ["0.100", "0.150", "0.100", "0.150", "0.100", "0.150"]
    metrics = analyze_quantization_grid(
        values,
        profile=profile_column("signal", values),
    )

    assert metrics.total_count == 6
    assert metrics.candidate_risk is None


def test_related_grid_overlap_is_jaccard_and_auditable():
    metrics = analyze_quantization_grid(
        ["0.00", "0.05", "0.10", "0.15"],
        profile=profile_column("signal_a", ["0.00", "0.05", "0.10", "0.15"]),
        comparison_values=["0.10", "0.15", "0.20", "0.25"],
    )

    assert metrics.grid_overlap == pytest.approx(2 / 6)


def test_detector_has_no_toy_filename_privilege(tmp_path):
    generic_path = tmp_path / "generic_measurements.csv"
    _write_csv(generic_path, _quantized_values())

    results = detect_quantization_grid(
        generic_path,
        _rule(),
        options={"file_path": generic_path, "value_column": "signal"},
    )

    assert len(results) == 1
    assert results[0].risk_level == "medium"


def test_measurement_precision_rule_is_active_and_points_to_detector():
    rule = _rule()

    assert rule.status == "active"
    assert rule.runtime_status == "active"
    assert rule.execution_mode == "offline"
    assert rule.risk_ceiling == "medium"
    assert rule.toy_fixture == "examples/toy_table_package/toy_quantized_timeseries.csv"
    assert rule.detector_module == "integrity_agent.detectors.numeric.quantization_grid"
    assert rule.detector_function == "detect_quantization_grid"
    assert "declared_resolution" in rule.input_requirement.fields_required
