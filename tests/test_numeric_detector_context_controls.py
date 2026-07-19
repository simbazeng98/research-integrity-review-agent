from __future__ import annotations

from pathlib import Path

from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.numeric.fixed_delta import detect_fixed_delta
from integrity_agent.detectors.numeric.terminal_digit import detect_terminal_digits


def _rules():
    project_root = Path(__file__).resolve().parents[1]
    return load_rule_registry(project_root / "knowledge_base" / "detector_rules")


def _write_table(path: Path, header: str, rows: list[str]) -> Path:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_terminal_digit_toy_filename_never_promotes_a_small_sample(tmp_path: Path):
    table = _write_table(
        tmp_path / "toy_terminal_digit_anomaly.csv",
        "measurement",
        [f"{index}.7" for index in range(1, 9)],
    )
    rule = _rules()["numeric_terminal_digit_anomaly"]

    findings = detect_terminal_digits(table, rule, options={"file_path": table})

    assert len(findings) == 1
    assert findings[0].risk_level == "low"
    assert findings[0].finding_id.startswith("RR-TD-")
    assert findings[0].metadata["sample_size"] == 8
    assert findings[0].metadata["open_for_scoring"] is False


def test_terminal_digit_skips_ids_rows_formulas_derived_and_normalized_columns(
    tmp_path: Path,
):
    table = _write_table(
        tmp_path / "context_columns.csv",
        "sample_id,row_index,formula_value,derived_value,normalized_signal",
        [f"{index * 10 + 7},{index * 10 + 7},{index}.7,{index + 10}.7,{index + 20}.7" for index in range(20)],
    )
    rule = _rules()["numeric_terminal_digit_anomaly"]
    options = {
        "file_path": table,
        "column_contexts": {
            "formula_value": {"role": "declared_formula"},
            "derived_value": {"role": "derived"},
            "normalized_signal": {"role": "normalization"},
        },
    }

    assert detect_terminal_digits(table, rule, options=options) == []


def test_terminal_digit_large_independent_measurement_retains_separate_evidence(
    tmp_path: Path,
):
    table = _write_table(
        tmp_path / "measurements.csv",
        "replicate_measurement",
        [f"{index}.7" for index in range(1, 21)],
    )
    rule = _rules()["numeric_terminal_digit_anomaly"]

    findings = detect_terminal_digits(
        table,
        rule,
        options={
            "file_path": table,
            "table_id": "tbl-measurements",
            "column_contexts": {
                "replicate_measurement": {"role": "independent_measurement"},
            },
        },
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.risk_level == "medium"
    assert finding.metadata["open_for_scoring"] is True
    assert finding.metadata["method_family"] == "numeric_pattern"
    assert finding.metadata["correlation_group"]
    assert "probability" in finding.metadata["correlation_notice"].lower()


def test_fixed_delta_without_independence_semantics_is_a_non_scoring_question(
    tmp_path: Path,
):
    table = _write_table(
        tmp_path / "undocumented_columns.csv",
        "reported_a,reported_b",
        [f"{index},{index + 2.5}" for index in range(1, 21)],
    )
    rule = _rules()["numeric_fixed_delta_between_columns"]

    findings = detect_fixed_delta(table, rule, options={"file_path": table})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.risk_level == "low"
    assert finding.metadata["record_type"] == "context_question"
    assert finding.metadata["open_for_scoring"] is False
    assert finding.metadata["mrpi_eligible"] is False
    assert finding.metadata["nominally_independent_measurements"] is False


def test_fixed_delta_only_scores_explicit_independent_measurements(tmp_path: Path):
    table = _write_table(
        tmp_path / "independent_replicates.csv",
        "replicate_a,replicate_b",
        [f"{index},{index + 2.5}" for index in range(1, 21)],
    )
    rule = _rules()["numeric_fixed_delta_between_columns"]

    findings = detect_fixed_delta(
        table,
        rule,
        options={
            "file_path": table,
            "table_id": "tbl-independent",
            "independent_measurement_columns": ["replicate_a", "replicate_b"],
        },
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.risk_level == "medium"
    assert finding.metadata["record_type"] == "integrity_finding"
    assert finding.metadata["open_for_scoring"] is True
    assert finding.metadata["mrpi_eligible"] is True
    assert finding.metadata["nominally_independent_measurements"] is True
    assert finding.metadata["method_family"] == "numeric_pattern"


def test_fixed_delta_small_explicit_independent_sample_is_never_medium(tmp_path: Path):
    table = _write_table(
        tmp_path / "toy_numeric_fixed_delta.csv",
        "replicate_a,replicate_b",
        ["1,3.5", "2,4.5", "3,5.5"],
    )
    rule = _rules()["numeric_fixed_delta_between_columns"]

    findings = detect_fixed_delta(
        table,
        rule,
        options={
            "file_path": table,
            "independent_measurement_columns": ["replicate_a", "replicate_b"],
        },
    )

    assert len(findings) <= 1
    assert not findings or findings[0].risk_level == "low"
    if findings:
        assert findings[0].metadata["open_for_scoring"] is False


def test_fixed_delta_suppresses_declared_formula_normalization_and_unit_conversion(
    tmp_path: Path,
):
    rule = _rules()["numeric_fixed_delta_between_columns"]

    formula_table = _write_table(
        tmp_path / "declared_formula.csv",
        "raw_value,formula_value",
        [f"{index},{index + 2.5}" for index in range(1, 21)],
    )
    assert detect_fixed_delta(
        formula_table,
        rule,
        options={
            "file_path": formula_table,
            "column_contexts": {
                "raw_value": {"role": "independent_measurement"},
                "formula_value": {"role": "declared_formula"},
            },
        },
    ) == []

    normalized_table = _write_table(
        tmp_path / "normalized.csv",
        "raw_signal,normalized_signal",
        [f"{index},{index + 10}" for index in range(1, 21)],
    )
    assert detect_fixed_delta(
        normalized_table,
        rule,
        options={"file_path": normalized_table},
    ) == []

    temperature_table = _write_table(
        tmp_path / "temperature.csv",
        "temperature_c,temperature_k",
        [f"{index},{index + 273.15}" for index in range(20, 40)],
    )
    assert detect_fixed_delta(
        temperature_table,
        rule,
        options={"file_path": temperature_table},
    ) == []


def test_fixed_delta_rule_is_delta_only_and_context_gated():
    rule = _rules()["numeric_fixed_delta_between_columns"]
    detection_contract = " ".join(rule.detection_idea).lower()

    assert "ratio" not in detection_contract
    assert "delta" in detection_contract or "difference" in detection_contract
    assert "independent" in detection_contract
