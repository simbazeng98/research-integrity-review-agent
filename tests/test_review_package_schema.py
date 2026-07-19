from __future__ import annotations

from integrity_agent.core.packages.package_schema import (
    ReviewPackageInput,
    EvidenceModuleStatus,
    ReviewPackageManifest,
    ReviewPackageRunSummary,
)

def test_review_package_schema_to_dict():
    pkg_in = ReviewPackageInput(
        package_dir="examples/toy_review_package",
        metadata_dir="examples/toy_review_package/metadata",
        images_dir="examples/toy_review_package/images",
        tables_dir="examples/toy_review_package/tables",
        pv_dir="examples/toy_review_package/pv",
        raw_pv_dir="examples/toy_review_package/raw_pv"
    )
    d_in = pkg_in.to_dict()
    assert d_in["package_dir"] == "examples/toy_review_package"
    assert d_in["metadata_dir"] == "examples/toy_review_package/metadata"

    status = EvidenceModuleStatus(
        module_name="reader-intake",
        status="success",
        input_path="examples/toy_review_package/metadata/doi.txt",
        output_paths=["outputs/review_package/paper_case/metadata.json"],
        warnings=["some warning"],
        runtime_seconds=1.23
    )
    d_status = status.to_dict()
    assert d_status["module_name"] == "reader-intake"
    assert d_status["status"] == "success"
    assert d_status["runtime_seconds"] == 1.23

    manifest = ReviewPackageManifest(
        package_id="toy_review_package",
        inputs=pkg_in,
        created_at=1700000000.0,
        version="v0.2.0",
        metadata_info={"doi": "10.1002/adma.202000000"}
    )
    d_manifest = manifest.to_dict()
    assert d_manifest["package_id"] == "toy_review_package"
    assert d_manifest["version"] == "v0.2.0"
    assert d_manifest["metadata_info"]["doi"] == "10.1002/adma.202000000"

    summary = ReviewPackageRunSummary(
        manifest=manifest,
        module_statuses=[status],
        overall_status="success",
        total_runtime_seconds=5.0,
        findings_summary={"low": 1, "medium": 0, "high": 0}
    )
    d_summary = summary.to_dict()
    assert d_summary["overall_status"] == "success"
    assert d_summary["total_runtime_seconds"] == 5.0
    assert d_summary["findings_summary"]["low"] == 1
