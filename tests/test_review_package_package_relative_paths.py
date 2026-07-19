from __future__ import annotations

import json

from integrity_agent.workflows.review_package import run_review_package
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _module_status(summary, name):
    return next(status.to_dict() for status in summary.module_statuses if status.module_name == name)


def test_review_package_resolves_package_relative_tables_and_pv_inputs(tmp_path, capsys):
    package_dir = tmp_path / "package"
    tables_dir = package_dir / "tables"
    pv_dir = package_dir / "pv"
    tables_dir.mkdir(parents=True)
    pv_dir.mkdir()

    (tables_dir / "numeric.csv").write_text(
        "measurement,comparison\n"
        "10,20\n"
        "20,30\n"
        "30,40\n"
        "40,50\n"
        "50,60\n",
        encoding="utf-8",
    )
    (pv_dir / "metrics.csv").write_text(
        "Device ID,Voc (V),Jsc (mA/cm2),FF (%),PCE (%)\n"
        "device-1,1.10,22.0,75.0,25.0\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_raw_pv=True,
    )
    captured = capsys.readouterr()

    assert "File not found: tables/numeric.csv" not in captured.err
    assert "File not found: pv/metrics.csv" not in captured.err

    unified_path = output_dir / "unified_evidence_index.jsonl"
    findings = _read_jsonl(unified_path)
    rule_ids = {finding.get("rule_id") for finding in findings}
    assert "numeric_fixed_delta_between_columns" in rule_ids
    assert "numeric_terminal_digit_anomaly" in rule_ids
    assert "pv_pce_consistency" in rule_ids
    assert validate_ledger_file(unified_path).ok

    table_status = _module_status(summary, "table-numeric-review")
    assert table_status["status"] == "success"
    assert table_status["input_artifact_count"] == 1
    assert table_status["parsed_row_count"] == 5
    assert table_status["finding_count"] >= 2
    assert table_status["skip_reason"] is None

    pv_status = _module_status(summary, "pv-domain-review")
    assert pv_status["status"] == "success"
    assert pv_status["input_artifact_count"] == 1
    assert pv_status["parsed_row_count"] == 1
    assert pv_status["finding_count"] >= 1
    assert pv_status["skip_reason"] is None


def test_review_package_distinguishes_no_input_zero_findings_and_zero_parse(tmp_path):
    no_input_package = tmp_path / "no_input"
    (no_input_package / "tables").mkdir(parents=True)
    no_input_summary = run_review_package(
        package_dir=str(no_input_package),
        output_dir=str(tmp_path / "no_input_output"),
        skip_images=True,
        skip_pv=True,
        skip_raw_pv=True,
    )
    no_input_status = _module_status(no_input_summary, "table-numeric-review")
    assert no_input_status["status"] == "skipped"
    assert no_input_status["input_artifact_count"] == 0
    assert no_input_status["parsed_row_count"] == 0
    assert no_input_status["finding_count"] == 0
    assert no_input_status["skip_reason"] == "no_input_artifacts"

    parsed_package = tmp_path / "parsed_without_findings"
    parsed_tables = parsed_package / "tables"
    parsed_tables.mkdir(parents=True)
    (parsed_tables / "notes.csv").write_text(
        "unrelated_metadata\nalpha\nbeta\n",
        encoding="utf-8",
    )
    parsed_summary = run_review_package(
        package_dir=str(parsed_package),
        output_dir=str(tmp_path / "parsed_output"),
        skip_images=True,
        skip_pv=True,
        skip_raw_pv=True,
    )
    parsed_status = _module_status(parsed_summary, "table-numeric-review")
    assert parsed_status["status"] == "success"
    assert parsed_status["input_artifact_count"] == 1
    assert parsed_status["parsed_row_count"] == 2
    assert parsed_status["finding_count"] == 0
    assert parsed_status["skip_reason"] is None

    failed_package = tmp_path / "failed_to_parse"
    failed_tables = failed_package / "tables"
    failed_tables.mkdir(parents=True)
    (failed_tables / "broken.xlsx").write_text("not an xlsx workbook", encoding="utf-8")
    failed_summary = run_review_package(
        package_dir=str(failed_package),
        output_dir=str(tmp_path / "failed_output"),
        skip_images=True,
        skip_pv=True,
        skip_raw_pv=True,
    )
    failed_status = _module_status(failed_summary, "table-numeric-review")
    assert failed_status["status"] in {"warning", "failed"}
    assert failed_status["input_artifact_count"] == 1
    assert failed_status["parsed_row_count"] == 0
    assert failed_status["finding_count"] == 0
    assert failed_status["skip_reason"]
