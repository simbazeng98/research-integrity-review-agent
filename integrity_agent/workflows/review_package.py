from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import time
import traceback

from integrity_agent.core.path_display import display_path
import sys

from integrity_agent.core.packages.package_schema import (
    ReviewPackageInput,
    EvidenceModuleStatus,
    ReviewPackageManifest,
    ReviewPackageRunSummary,
)
from integrity_agent.workflows.reader_intake import run_reader_intake
from integrity_agent.workflows.image_intake import run_image_intake
from integrity_agent.workflows.image_similarity import run_image_similarity
from integrity_agent.workflows.table_intake import run_table_intake
from integrity_agent.workflows.table_numeric_review import run_table_numeric_review
from integrity_agent.workflows.pv_domain_review import run_pv_domain_review
from integrity_agent.workflows.raw_pv_reconciliation import run_raw_pv_reconciliation
from integrity_agent.workflows.report_reader_review import write_reader_review_report
from integrity_agent.workflows.report_review_package_html import run_report_review_package_html

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Run paper/package-level evidence review.")
    parser.add_argument("package_dir", help="Path to package directory (e.g. examples/toy_review_package).")
    parser.add_argument("--skip-images", action="store_true", help="Skip image intake and similarity modules.")
    parser.add_argument("--skip-tables", action="store_true", help="Skip table intake and numeric reviews.")
    parser.add_argument("--skip-pv", action="store_true", help="Skip PV domain review module.")
    parser.add_argument("--skip-raw-pv", action="store_true", help="Skip raw PV recalculation module.")
    parser.add_argument("--allow-network", action="store_true", help="Allow network requests for metadata checks.")
    parser.add_argument("-o", "--output-dir", default="outputs/review_package", help="Directory to write output files.")
    return parser.parse_args(args)

def safe_copy_file(src: Path | str, dest: Path | str) -> None:
    src_p = Path(src)
    dest_p = Path(dest)
    if src_p.exists():
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dest_p)

def safe_copy_dir(src: Path | str, dest: Path | str) -> None:
    src_p = Path(src)
    dest_p = Path(dest)
    if src_p.exists():
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        if dest_p.exists():
            shutil.rmtree(dest_p)
        shutil.copytree(src_p, dest_p)

def run_review_package(
    package_dir: str,
    skip_images: bool = False,
    skip_tables: bool = False,
    skip_pv: bool = False,
    skip_raw_pv: bool = False,
    allow_network: bool = False,
    output_dir: str = "outputs/review_package",
) -> ReviewPackageRunSummary:
    start_time = time.time()
    
    pack_path = Path(package_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    package_id = pack_path.name
    pkg_input = ReviewPackageInput(
        package_dir=str(pack_path),
        metadata_dir=str(pack_path / "metadata"),
        images_dir=str(pack_path / "images"),
        tables_dir=str(pack_path / "tables"),
        pv_dir=str(pack_path / "pv"),
        raw_pv_dir=str(pack_path / "raw_pv")
    )

    manifest = ReviewPackageManifest(
        package_id=package_id,
        inputs=pkg_input,
        created_at=start_time
    )

    module_statuses: list[EvidenceModuleStatus] = []

    # 1. Metadata Intake
    doi_file = Path(pkg_input.metadata_dir) / "doi.txt"
    if doi_file.exists():
        m_start = time.time()
        try:
            with open(doi_file, "r", encoding="utf-8") as f:
                doi = f.read().strip()
            
            if doi:
                meta_json, intake_md = run_reader_intake(
                    doi_input=doi,
                    allow_network=allow_network,
                    output_dir="outputs/paper_case"
                )
                
                # Copy to output_dir
                safe_copy_file(meta_json, out_path / "paper_case/metadata.json")
                safe_copy_file(intake_md, out_path / "paper_case/intake_summary.md")
                
                module_statuses.append(EvidenceModuleStatus(
                    module_name="reader-intake",
                    status="success",
                    input_path=str(doi_file),
                    output_paths=[
                        str(out_path / "paper_case/metadata.json"),
                        str(out_path / "paper_case/intake_summary.md")
                    ],
                    runtime_seconds=time.time() - m_start
                ))
            else:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="reader-intake",
                    status="warning",
                    input_path=str(doi_file),
                    warnings=["Empty DOI file"],
                    runtime_seconds=time.time() - m_start
                ))
        except Exception as e:
            module_statuses.append(EvidenceModuleStatus(
                module_name="reader-intake",
                status="failed",
                input_path=str(doi_file),
                error_message=str(e) + "\n" + traceback.format_exc(),
                runtime_seconds=time.time() - m_start
            ))
    else:
        module_statuses.append(EvidenceModuleStatus(
            module_name="reader-intake",
            status="skipped",
            warnings=["No metadata/doi.txt found"]
        ))

    # 2. Image Intake & Similarity
    if skip_images or not Path(pkg_input.images_dir).exists():
        module_statuses.append(EvidenceModuleStatus(
            module_name="image-intake",
            status="skipped",
            warnings=["Skipped by configuration or missing folder"]
        ))
        module_statuses.append(EvidenceModuleStatus(
            module_name="image-similarity",
            status="skipped",
            warnings=["Skipped by configuration or missing folder"]
        ))
    else:
        # Image Intake
        m_start = time.time()
        try:
            manifest_jsonl, manifest_csv, findings_jsonl, summary_md = run_image_intake(
                folder_path=pkg_input.images_dir,
                output_dir="outputs/image_intake"
            )
            
            safe_copy_file(manifest_jsonl, out_path / "image_intake/image_manifest.jsonl")
            safe_copy_file(manifest_csv, out_path / "image_intake/image_manifest.csv")
            safe_copy_file(findings_jsonl, out_path / "image_intake/image_findings.jsonl")
            safe_copy_file(summary_md, out_path / "image_intake/image_intake_summary.md")

            module_statuses.append(EvidenceModuleStatus(
                module_name="image-intake",
                status="success",
                input_path=pkg_input.images_dir,
                output_paths=[
                    str(out_path / "image_intake/image_manifest.jsonl"),
                    str(out_path / "image_intake/image_findings.jsonl")
                ],
                runtime_seconds=time.time() - m_start
            ))

            # Image Similarity
            sim_start = time.time()
            try:
                hashes_jsonl, candidates_jsonl, sim_summary_md = run_image_similarity(
                    manifest_jsonl_path="outputs/image_intake/image_manifest.jsonl",
                    output_dir="outputs/image_intake",
                    threshold=6,
                    hash_method="dhash"
                )
                
                safe_copy_file(hashes_jsonl, out_path / "image_intake/image_hashes.jsonl")
                safe_copy_file(candidates_jsonl, out_path / "image_intake/image_similarity_candidates.jsonl")
                safe_copy_file(sim_summary_md, out_path / "image_intake/image_similarity_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="image-similarity",
                    status="success",
                    input_path="outputs/image_intake/image_manifest.jsonl",
                    output_paths=[
                        str(out_path / "image_intake/image_hashes.jsonl"),
                        str(out_path / "image_intake/image_similarity_candidates.jsonl")
                    ],
                    runtime_seconds=time.time() - sim_start
                ))
            except Exception as sim_err:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="image-similarity",
                    status="failed",
                    input_path="outputs/image_intake/image_manifest.jsonl",
                    error_message=str(sim_err),
                    runtime_seconds=time.time() - sim_start
                ))

        except Exception as e:
            module_statuses.append(EvidenceModuleStatus(
                module_name="image-intake",
                status="failed",
                input_path=pkg_input.images_dir,
                error_message=str(e),
                runtime_seconds=time.time() - m_start
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="image-similarity",
                status="failed",
                error_message="Parent image-intake failed",
                runtime_seconds=0.0
            ))

    # 3. Table Intake & Numeric Review
    if skip_tables or not Path(pkg_input.tables_dir).exists():
        module_statuses.append(EvidenceModuleStatus(
            module_name="table-intake",
            status="skipped"
        ))
        module_statuses.append(EvidenceModuleStatus(
            module_name="table-numeric-review",
            status="skipped"
        ))
    else:
        m_start = time.time()
        try:
            t_manifest_jsonl, t_manifest_csv, t_profiles_jsonl, t_summary_md = run_table_intake(
                input_dir=pkg_input.tables_dir,
                output_dir="outputs/table_intake"
            )
            
            safe_copy_file(t_manifest_jsonl, out_path / "table_intake/table_manifest.jsonl")
            safe_copy_file(t_manifest_csv, out_path / "table_intake/table_manifest.csv")
            safe_copy_file(t_profiles_jsonl, out_path / "table_intake/column_profiles.jsonl")
            safe_copy_file(t_summary_md, out_path / "table_intake/table_intake_summary.md")

            module_statuses.append(EvidenceModuleStatus(
                module_name="table-intake",
                status="success",
                input_path=pkg_input.tables_dir,
                output_paths=[
                    str(out_path / "table_intake/table_manifest.jsonl"),
                    str(out_path / "table_intake/column_profiles.jsonl")
                ],
                runtime_seconds=time.time() - m_start
            ))

            # Table Numeric Review
            num_start = time.time()
            try:
                num_findings_jsonl, num_summary_md = run_table_numeric_review(
                    manifest_jsonl_path="outputs/table_intake/table_manifest.jsonl",
                    output_dir="outputs/table_intake"
                )
                
                safe_copy_file(num_findings_jsonl, out_path / "table_intake/table_numeric_findings.jsonl")
                safe_copy_file(num_summary_md, out_path / "table_intake/table_numeric_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="table-numeric-review",
                    status="success",
                    input_path="outputs/table_intake/table_manifest.jsonl",
                    output_paths=[
                        str(out_path / "table_intake/table_numeric_findings.jsonl")
                    ],
                    runtime_seconds=time.time() - num_start
                ))
            except Exception as num_err:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="table-numeric-review",
                    status="failed",
                    input_path="outputs/table_intake/table_manifest.jsonl",
                    error_message=str(num_err),
                    runtime_seconds=time.time() - num_start
                ))

        except Exception as e:
            module_statuses.append(EvidenceModuleStatus(
                module_name="table-intake",
                status="failed",
                input_path=pkg_input.tables_dir,
                error_message=str(e),
                runtime_seconds=time.time() - m_start
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="table-numeric-review",
                status="failed",
                error_message="Parent table-intake failed",
                runtime_seconds=0.0
            ))

    # 4. PV Domain Review
    if skip_pv or not Path(pkg_input.pv_dir).exists():
        module_statuses.append(EvidenceModuleStatus(
            module_name="pv-domain-review",
            status="skipped"
        ))
    else:
        m_start = time.time()
        try:
            # Intake the PV directory first
            pv_t_manifest_jsonl, pv_t_manifest_csv, pv_t_profiles_jsonl, pv_t_summary_md = run_table_intake(
                input_dir=pkg_input.pv_dir,
                output_dir="outputs/pv_domain_intake"
            )

            metric_rows, field_mapping, findings, summary = run_pv_domain_review(
                manifest_path=pv_t_manifest_jsonl,
                column_profiles_path=pv_t_profiles_jsonl,
                output_dir="outputs/pv_domain"
            )
            
            safe_copy_file(metric_rows, out_path / "pv_domain/pv_metric_rows.jsonl")
            safe_copy_file(field_mapping, out_path / "pv_domain/pv_field_mappings.jsonl")
            safe_copy_file(findings, out_path / "pv_domain/pv_findings.jsonl")
            safe_copy_file(summary, out_path / "pv_domain/pv_domain_summary.md")

            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-domain-review",
                status="success",
                input_path=pkg_input.pv_dir,
                output_paths=[
                    str(out_path / "pv_domain/pv_findings.jsonl")
                ],
                runtime_seconds=time.time() - m_start
            ))
        except Exception as e:
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-domain-review",
                status="failed",
                input_path=pkg_input.pv_dir,
                error_message=str(e),
                runtime_seconds=time.time() - m_start
            ))

    # 5. Raw PV Reconciliation
    if skip_raw_pv or not Path(pkg_input.raw_pv_dir).exists():
        module_statuses.append(EvidenceModuleStatus(
            module_name="raw-pv-reconcile",
            status="skipped"
        ))
    else:
        m_start = time.time()
        try:
            run_raw_pv_reconciliation(
                package_dir=pkg_input.raw_pv_dir,
                output_dir="outputs/raw_pv"
            )
            
            # Copy all files from outputs/raw_pv to output_dir/raw_pv/
            safe_copy_file("outputs/raw_pv/raw_pv_findings.jsonl", out_path / "raw_pv/raw_pv_findings.jsonl")
            safe_copy_file("outputs/raw_pv/raw_pv_reconciliation_summary.md", out_path / "raw_pv/raw_pv_reconciliation_summary.md")
            safe_copy_file("outputs/raw_pv/jv_metrics.jsonl", out_path / "raw_pv/jv_metrics.jsonl")
            safe_copy_file("outputs/raw_pv/eqe_integration_results.jsonl", out_path / "raw_pv/eqe_integration_results.jsonl")
            safe_copy_file("outputs/raw_pv/excel_formula_audit.jsonl", out_path / "raw_pv/excel_formula_audit.jsonl")

            module_statuses.append(EvidenceModuleStatus(
                module_name="raw-pv-reconcile",
                status="success",
                input_path=pkg_input.raw_pv_dir,
                output_paths=[
                    str(out_path / "raw_pv/raw_pv_findings.jsonl")
                ],
                runtime_seconds=time.time() - m_start
            ))
        except Exception as e:
            module_statuses.append(EvidenceModuleStatus(
                module_name="raw-pv-reconcile",
                status="failed",
                input_path=pkg_input.raw_pv_dir,
                error_message=str(e),
                runtime_seconds=time.time() - m_start
            ))

    # 6. Unified Evidence Index Aggregation
    index_start = time.time()
    unified_findings = []
    processed_keys = set()

    finding_files = [
        "outputs/rule_findings.jsonl",
        "outputs/image_intake/image_findings.jsonl",
        "outputs/image_intake/image_similarity_candidates.jsonl",
        "outputs/table_intake/table_numeric_findings.jsonl",
        "outputs/pv_domain/pv_findings.jsonl",
        "outputs/raw_pv/raw_pv_findings.jsonl"
    ]

    finding_counter = 1
    for ff in finding_files:
        ff_path = Path(ff)
        if ff_path.exists():
            try:
                with open(ff_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            d = json.loads(line)
                            
                            # Standardize finding format
                            rule_id = d.get("rule_id", "unknown_rule")
                            src = d.get("source_file") or d.get("relative_path") or d.get("relative_path_a")
                            if not src and d.get("evidence_items"):
                                src = d["evidence_items"][0].get("source") or d["evidence_items"][0].get("relative_path")
                            if not src:
                                src = "unknown_file"
                                
                            d["source_file"] = src
                            safe_lang = d.get("safe_report_language", "")
                            comp_key = (rule_id, src, safe_lang)
                            
                            if comp_key in processed_keys:
                                continue
                            processed_keys.add(comp_key)
                            
                            # Ensure finding has finding_id
                            if "finding_id" not in d:
                                d["finding_id"] = f"UNIFIED-FIND-{finding_counter:03d}"
                                finding_counter += 1
                                
                            unified_findings.append(d)
            except Exception as e:
                print(f"WARNING: failed to read findings from {ff}: {e}", file=sys.stderr)

    # Write unified evidence index
    unified_index_path = out_path / "unified_evidence_index.jsonl"
    with open(unified_index_path, "w", encoding="utf-8") as f:
        for finding in unified_findings:
            f.write(json.dumps(finding, ensure_ascii=False) + "\n")

    # Group counts
    findings_summary = {"low": 0, "medium": 0, "high": 0}
    for f in unified_findings:
        rl = f.get("risk_level", "low").lower()
        if rl in findings_summary:
            findings_summary[rl] += 1
        else:
            findings_summary["low"] += 1

    module_statuses.append(EvidenceModuleStatus(
        module_name="unified-evidence-index",
        status="success",
        output_paths=[str(unified_index_path)],
        runtime_seconds=time.time() - index_start
    ))

    # 7. Final Reader Report
    report_start = time.time()
    summary_md_path = out_path / "review_package_summary.md"
    try:
        write_reader_review_report(
            findings_path=unified_index_path,
            output_path=summary_md_path
        )
        module_statuses.append(EvidenceModuleStatus(
            module_name="report-reader-review",
            status="success",
            input_path=str(unified_index_path),
            output_paths=[str(summary_md_path)],
            runtime_seconds=time.time() - report_start
        ))
    except Exception as e:
        module_statuses.append(EvidenceModuleStatus(
            module_name="report-reader-review",
            status="failed",
            input_path=str(unified_index_path),
            error_message=str(e),
            runtime_seconds=time.time() - report_start
        ))

    # 8. HTML Dashboard
    dash_start = time.time()
    dashboard_html_path = out_path / "review_package_dashboard.html"
    try:
        run_report_review_package_html(
            unified_index=str(unified_index_path),
            output_path=str(dashboard_html_path)
        )
        module_statuses.append(EvidenceModuleStatus(
            module_name="report-review-package-html",
            status="success",
            input_path=str(unified_index_path),
            output_paths=[str(dashboard_html_path)],
            runtime_seconds=time.time() - dash_start
        ))
    except Exception as e:
        module_statuses.append(EvidenceModuleStatus(
            module_name="report-review-package-html",
            status="failed",
            input_path=str(unified_index_path),
            error_message=str(e),
            runtime_seconds=time.time() - dash_start
        ))

    # Compile run summary
    total_runtime = time.time() - start_time
    overall_status = "success"
    if any(s.status == "failed" for s in module_statuses):
        overall_status = "failed"
    elif any(s.status == "warning" for s in module_statuses):
        overall_status = "warning"

    run_summary = ReviewPackageRunSummary(
        manifest=manifest,
        module_statuses=module_statuses,
        overall_status=overall_status,
        total_runtime_seconds=total_runtime,
        findings_summary=findings_summary
    )

    # Write review_package_manifest.json
    manifest_json_path = out_path / "review_package_manifest.json"
    with open(manifest_json_path, "w", encoding="utf-8") as f:
        json.dump(run_summary.to_dict(), f, indent=2, ensure_ascii=False)

    # Write module_status.jsonl
    module_status_path = out_path / "module_status.jsonl"
    with open(module_status_path, "w", encoding="utf-8") as f:
        for s in module_statuses:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

    print(f"Wrote unified package manifest: {display_path(manifest_json_path)}")
    print(f"Wrote module statuses: {display_path(module_status_path)}")
    print(f"Unified evidence review completed in {total_runtime:.2f}s with status {overall_status}.")
    return run_summary

def main(args=None):
    parsed = parse_args(args)
    
    # Map raw-pv argument back to python variable name
    run_review_package(
        package_dir=parsed.package_dir,
        skip_images=parsed.skip_images,
        skip_tables=parsed.skip_tables,
        skip_pv=parsed.skip_pv,
        skip_raw_pv=parsed.skip_raw_pv,
        allow_network=parsed.allow_network,
        output_dir=parsed.output_dir
    )

if __name__ == "__main__":
    main()
