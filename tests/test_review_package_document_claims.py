from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from integrity_agent.workflows.review_package import run_review_package
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_review_package_keeps_document_claim_context_in_final_outputs(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    package_dir = tmp_path / "package"
    shutil.copytree(
        project_root / "examples" / "toy_review_package" / "documents",
        package_dir / "documents",
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

    unified_path = output_dir / "unified_evidence_index.jsonl"
    assert summary.overall_status != "failed"
    assert validate_ledger_file(unified_path).ok

    records = _records(unified_path)
    record = next(
        item
        for item in records
        if item.get("rule_id") == "cross_document_claim_consistency"
    )
    assert record["provenance"]["human_confirmed"] is True
    assert record["provenance"]["source_version"] == "publisher-v1"
    # A deterministic comparison followed by current-version reconciliation is
    # E3: current-version/counter-evidence has been compared, but no formal
    # correction is inferred.
    assert record["evidence_tier"] == "E3"

    report = (output_dir / "review_package_summary.md").read_text(encoding="utf-8")
    dashboard = (output_dir / "review_package_dashboard.html").read_text(
        encoding="utf-8"
    )
    for rendered in (report, dashboard):
        assert "publisher-v1" in rendered
        assert "E3" in rendered


def _status(summary, module_name: str) -> dict:
    return next(
        status.to_dict()
        for status in summary.module_statuses
        if status.module_name == module_name
    )


def test_review_package_integrates_structured_decay_curve_and_lineage_sidecars(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    tables_dir = package_dir / "tables"
    documents_dir.mkdir(parents=True)
    tables_dir.mkdir()

    decay_records = [
        {
            "record_id": "trpl-figure",
            "claim_id": "trpl-figure",
            "decay_type": "trpl",
            "sample_id": "sample-A",
            "source_version": "si-v1",
            "source_document": "figure_annotation",
            "source": "documents/decay_fit_records.jsonl",
            "location": "Figure S2 annotation",
            "reported_average": 2.4,
            "reported_unit": "us",
            "declared_formula": "amplitude_weighted",
            "components": [],
            "human_confirmed": True,
        },
        {
            "record_id": "trpl-parameters",
            "claim_id": "trpl-parameters",
            "decay_type": "trpl",
            "sample_id": "sample-A",
            "source_version": "si-v1",
            "source_document": "source_parameters",
            "source": "tables/trpl_fit.csv",
            "location": "rows 2-3",
            "components": [
                {"amplitude": 1.0, "lifetime": 1.0, "unit": "us"},
                {"amplitude": 3.0, "lifetime": 2.0, "unit": "us"},
            ],
            "human_confirmed": True,
        },
    ]
    (documents_dir / "decay_fit_records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in decay_records),
        encoding="utf-8",
    )

    (tables_dir / "curve_source.csv").write_text(
        "voltage,current\n" + "".join(f"{i},{i * 2}\n" for i in range(8)),
        encoding="utf-8",
    )
    (tables_dir / "curve_plot.csv").write_text(
        "voltage,current\n"
        + "".join(f"{i},{i * 2}\n" for i in (0, 1, 5, 6, 7)),
        encoding="utf-8",
    )
    (documents_dir / "curve_reconciliations.yml").write_text(
        yaml.safe_dump(
            {
                "reconciliations": [
                    {
                        "source_table": {
                            "path": "tables/curve_source.csv",
                            "source_label": "tables/curve_source.csv",
                            "location": "source rows 2 onward",
                            "sample_id": "device-A",
                            "source_version": "publisher-v1",
                        },
                        "plot_table": {
                            "path": "tables/curve_plot.csv",
                            "source_label": "tables/curve_plot.csv",
                            "location": "plot rows 2 onward",
                            "sample_id": "device-A",
                            "source_version": "publisher-v1",
                        },
                        "mapping": {
                            "source_x": "voltage",
                            "source_y": "current",
                            "plot_x": "voltage",
                            "plot_y": "current",
                            "x_axis_kind": "voltage",
                        },
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (documents_dir / "materials_process_lineage.yml").write_text(
        yaml.safe_dump(
            {
                "records": [
                    {
                        "sample_id": "dispersion-A",
                        "source_file": "documents/materials_process_lineage.yml",
                        "location": "record 1",
                        "stages": [
                            "preparation",
                            "filtration",
                            "storage",
                            "dls",
                            "deposition",
                        ],
                        "measurement_stage": "after_filtration",
                        "distribution_basis": "intensity_weighted",
                        "nominal_pore_nm": 220,
                        "hydrodynamic_diameter_nm": 1000,
                        "human_confirmed": True,
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
        skip_raw_pv=True,
    )

    unified_path = output_dir / "unified_evidence_index.jsonl"
    unified = _records(unified_path)
    assert validate_ledger_file(unified_path).ok
    assert {
        "pv_decay_fit_consistency",
        "curve_point_coverage",
        "materials_sample_lineage",
    }.issubset({record.get("rule_id") for record in unified})
    assert str(package_dir.resolve()) not in unified_path.read_text(encoding="utf-8")

    expected_counts = {
        "pv-decay-fit-review": (2, 1),
        "curve-point-coverage": (1, 1),
        "materials-process-lineage": (1, 1),
    }
    for module_name, (parsed, findings) in expected_counts.items():
        status = _status(summary, module_name)
        assert status["status"] == "success"
        assert status["input_artifact_count"] == 1
        assert status["parsed_row_count"] == parsed
        assert status["finding_count"] == findings


def test_review_package_curve_path_failure_is_not_silent_success(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "curve_reconciliations.yml").write_text(
        yaml.safe_dump(
            {
                "reconciliations": [
                    {
                        "source_table": {
                            "path": "tables/missing-source.csv",
                            "location": "source rows",
                            "sample_id": "device-A",
                            "source_version": "v1",
                        },
                        "plot_table": {
                            "path": "tables/missing-plot.csv",
                            "location": "plot rows",
                            "sample_id": "device-A",
                            "source_version": "v1",
                        },
                        "mapping": {
                            "source_x": "voltage",
                            "source_y": "current",
                            "plot_x": "voltage",
                            "plot_y": "current",
                        },
                    }
                ]
            },
            sort_keys=False,
        ),
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

    status = _status(summary, "curve-point-coverage")
    assert status["status"] in {"warning", "failed"}
    assert status["input_artifact_count"] == 1
    assert status["parsed_row_count"] == 0
    assert status["skip_reason"]


def test_structured_sidecar_rejects_sensitive_auth_material(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    documents_dir.mkdir(parents=True)
    sensitive_assignment = "coo" + "kie=synthetic-redacted-value"
    (documents_dir / "materials_process_lineage.yml").write_text(
        yaml.safe_dump(
            {
                "records": [
                    {
                        "sample_id": "dispersion-A",
                        "source_file": "documents/materials_process_lineage.yml",
                        "location": "record 1",
                        "stages": ["preparation", "filtration", "dls"],
                        "measurement_stage": "after_filtration",
                        "distribution_basis": "intensity_weighted",
                        "nominal_pore_nm": 220,
                        "hydrodynamic_diameter_nm": 1000,
                        "notes": sensitive_assignment,
                        "human_confirmed": True,
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

    status = _status(summary, "materials-process-lineage")
    assert status["status"] == "failed"
    assert "sensitive authentication" in (status["error_message"] or "")
    assert "synthetic-redacted-value" not in (
        output_dir / "unified_evidence_index.jsonl"
    ).read_text(encoding="utf-8")
