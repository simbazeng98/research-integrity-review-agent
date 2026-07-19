from __future__ import annotations

import json

from integrity_agent.workflows.review_package import run_review_package


def test_review_package_passes_column_profiles_to_quantization_detector(tmp_path):
    package_dir = tmp_path / "package"
    tables_dir = package_dir / "tables"
    tables_dir.mkdir(parents=True)
    levels = ["0.100", "0.150", "0.200", "0.250", "0.300", "0.350", "0.400"]
    order = [0, 2, 1, 3, 3, 4, 2, 5, 1, 6, 4, 4, 3, 0, 2, 5] * 2
    (tables_dir / "timeseries.csv").write_text(
        "time_s,signal\n"
        + "".join(
            f"{index},{levels[level]}\n" for index, level in enumerate(order)
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    records = [
        json.loads(line)
        for line in (output_dir / "unified_evidence_index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    findings = [
        record
        for record in records
        if record.get("rule_id") == "measurement_precision_anomaly"
    ]
    assert len(findings) == 1
    assert findings[0]["metadata"]["profile_source"] == "provided"
    assert findings[0]["metadata"]["precision_hint"] == 0.001

    status = next(
        item.to_dict()
        for item in summary.module_statuses
        if item.module_name == "table-numeric-review"
    )
    assert status["status"] == "success"
    assert status["input_artifact_count"] == 1
    assert status["parsed_row_count"] == 32
    assert status["finding_count"] >= 1
