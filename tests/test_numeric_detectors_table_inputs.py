from __future__ import annotations

from pathlib import Path
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.detectors.numeric.fixed_delta import detect_fixed_delta
from integrity_agent.detectors.numeric.terminal_digit import detect_terminal_digits


def test_fixed_delta_on_custom_table():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    rule = registry["numeric_fixed_delta_between_columns"]
    
    # Run on synthetic toy csv
    csv_file = project_root / "examples" / "toy_table_package" / "toy_fixed_delta.csv"
    
    # Pass options with custom file path
    results = detect_fixed_delta(csv_file, rule, options={"file_path": csv_file})
    assert len(results) == 1
    assert results[0].rule_id == "numeric_fixed_delta_between_columns"
    assert "columns reported_a and reported_b" in results[0].evidence_items[0]["location"]


def test_terminal_digit_on_custom_table():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    rule = registry["numeric_terminal_digit_anomaly"]
    
    # Run on synthetic toy tsv
    tsv_file = project_root / "examples" / "toy_table_package" / "toy_terminal_digit.tsv"
    
    results = detect_terminal_digits(tsv_file, rule, options={"file_path": tsv_file})
    assert len(results) == 1
    assert results[0].rule_id == "numeric_terminal_digit_anomaly"
    assert "column measurement" in results[0].evidence_items[0]["location"]
    # Check sample size logic: total digits is 8, so risk level should be 'low'!
    assert results[0].risk_level == "low"
