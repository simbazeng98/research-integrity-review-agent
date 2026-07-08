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
    locale: str = "en",
) -> ReviewPackageRunSummary:
    import tempfile

    start_time = time.time()

    pack_path = Path(package_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Clean previous status-enrich outputs to prevent stale residual files
    status_enrich_out = out_path / "status_enrich"
    if status_enrich_out.exists():
        try:
            shutil.rmtree(status_enrich_out)
        except Exception:
            pass

    # Clean previous reference-scan outputs to prevent stale residual files
    reference_scan_out = out_path / "reference_scan"
    if reference_scan_out.exists():
        try:
            shutil.rmtree(reference_scan_out)
        except Exception:
            pass

    # Clean previous pv_ruleset_review outputs to prevent stale residual files
    pv_ruleset_review_out = out_path / "pv_ruleset_review"
    if pv_ruleset_review_out.exists():
        try:
            shutil.rmtree(pv_ruleset_review_out)
        except Exception:
            pass

    package_id = pack_path.name
    pkg_input = ReviewPackageInput(
        package_dir=str(pack_path),
        metadata_dir=str(pack_path / "metadata"),
        images_dir=str(pack_path / "images"),
        tables_dir=str(pack_path / "tables"),
        pv_dir=str(pack_path / "pv"),
        raw_pv_dir=str(pack_path / "raw_pv"),
        references_dir=str(pack_path / "references")
    )

    manifest = ReviewPackageManifest(
        package_id=package_id,
        inputs=pkg_input,
        created_at=start_time
    )

    module_statuses: list[EvidenceModuleStatus] = []

    # Collect manifests and profiles for PV ruleset review
    pv_ruleset_manifests = []
    pv_ruleset_profiles = []

    # Run-scoped temporary directory for intermediate workflows outputs
    temp_dir_obj = tempfile.TemporaryDirectory(prefix="integrity_run_")
    temp_dir = Path(temp_dir_obj.name)

    try:
        # 1. Metadata Intake
        doi_file = Path(pkg_input.metadata_dir) / "doi.txt"
        if doi_file.exists():
            # Reader Intake
            m_start = time.time()
            try:
                with open(doi_file, "r", encoding="utf-8") as f:
                    doi = f.read().strip()

                if doi:
                    meta_json, intake_md = run_reader_intake(
                        doi_input=doi,
                        allow_network=allow_network,
                        output_dir=temp_dir / "paper_case"
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

            # Status Enrichment
            se_start = time.time()
            try:
                from integrity_agent.workflows.status_enrich import run_status_enrich
                se_jsonl, se_summary = run_status_enrich(
                    input_path=doi_file,
                    allow_network=allow_network,
                    output_dir=temp_dir / "status_enrich"
                )

                safe_copy_file(se_jsonl, out_path / "status_enrich/status_items.jsonl")
                safe_copy_file(se_summary, out_path / "status_enrich/status_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="status-enrich",
                    status="success",
                    input_path=str(doi_file),
                    output_paths=[
                        str(out_path / "status_enrich/status_items.jsonl"),
                        str(out_path / "status_enrich/status_summary.md")
                    ],
                    runtime_seconds=time.time() - se_start
                ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="status-enrich",
                    status="failed",
                    input_path=str(doi_file),
                    error_message=str(e) + "\n" + traceback.format_exc(),
                    runtime_seconds=time.time() - se_start
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="reader-intake",
                status="skipped",
                warnings=["No metadata/doi.txt found"]
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="status-enrich",
                status="skipped",
                warnings=["No metadata/doi.txt found"]
            ))

        # 1c. References / Bibliography Scan
        ref_start = time.time()
        ref_dir = Path(pkg_input.references_dir)
        ref_txt = ref_dir / "references.txt"
        ref_jsonl = ref_dir / "references.jsonl"

        # Check if references exist
        ref_file = None
        if ref_txt.exists():
            ref_file = ref_txt
        elif ref_jsonl.exists():
            ref_file = ref_jsonl

        if ref_file:
            try:
                from integrity_agent.workflows.reference_scan import run_reference_scan
                ref_jsonl_out, ref_summary_out = run_reference_scan(
                    input_path=ref_file,
                    allow_network=allow_network,
                    output_dir=temp_dir / "reference_scan"
                )

                safe_copy_file(ref_jsonl_out, out_path / "reference_scan/reference_anomalies.jsonl")
                safe_copy_file(ref_summary_out, out_path / "reference_scan/reference_anomaly_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="reference-scan",
                    status="success",
                    input_path=str(ref_file),
                    output_paths=[
                        str(out_path / "reference_scan/reference_anomalies.jsonl"),
                        str(out_path / "reference_scan/reference_anomaly_summary.md")
                    ],
                    runtime_seconds=time.time() - ref_start
                ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="reference-scan",
                    status="failed",
                    input_path=str(ref_file),
                    error_message=str(e) + "\n" + traceback.format_exc(),
                    runtime_seconds=time.time() - ref_start
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="reference-scan",
                status="skipped",
                warnings=["No references/references.txt or references/references.jsonl found"]
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
                    output_dir=temp_dir / "image_intake"
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
                        manifest_jsonl_path=temp_dir / "image_intake/image_manifest.jsonl",
                        output_dir=temp_dir / "image_intake",
                        threshold=6,
                        hash_method="dhash"
                    )

                    safe_copy_file(hashes_jsonl, out_path / "image_intake/image_hashes.jsonl")
                    safe_copy_file(candidates_jsonl, out_path / "image_intake/image_similarity_candidates.jsonl")
                    safe_copy_file(sim_summary_md, out_path / "image_intake/image_similarity_summary.md")

                    module_statuses.append(EvidenceModuleStatus(
                        module_name="image-similarity",
                        status="success",
                        input_path=str(out_path / "image_intake/image_manifest.jsonl"),
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
                        input_path=str(out_path / "image_intake/image_manifest.jsonl"),
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
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-ruleset-review",
                status="skipped"
            ))
        else:
            m_start = time.time()
            try:
                t_manifest_jsonl, t_manifest_csv, t_profiles_jsonl, t_summary_md = run_table_intake(
                    input_dir=pkg_input.tables_dir,
                    output_dir=temp_dir / "table_intake"
                )

                safe_copy_file(t_manifest_jsonl, out_path / "table_intake/table_manifest.jsonl")
                safe_copy_file(t_manifest_csv, out_path / "table_intake/table_manifest.csv")
                safe_copy_file(t_profiles_jsonl, out_path / "table_intake/column_profiles.jsonl")
                safe_copy_file(t_summary_md, out_path / "table_intake/table_intake_summary.md")

                pv_ruleset_manifests.append(t_manifest_jsonl)
                pv_ruleset_profiles.append(t_profiles_jsonl)

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
                        manifest_jsonl_path=temp_dir / "table_intake/table_manifest.jsonl",
                        output_dir=temp_dir / "table_intake"
                    )

                    safe_copy_file(num_findings_jsonl, out_path / "table_intake/table_numeric_findings.jsonl")
                    safe_copy_file(num_summary_md, out_path / "table_intake/table_numeric_summary.md")

                    module_statuses.append(EvidenceModuleStatus(
                        module_name="table-numeric-review",
                        status="success",
                        input_path=str(out_path / "table_intake/table_manifest.jsonl"),
                        output_paths=[
                            str(out_path / "table_intake/table_numeric_findings.jsonl")
                        ],
                        runtime_seconds=time.time() - num_start
                    ))
                except Exception as num_err:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="table-numeric-review",
                        status="failed",
                        input_path=str(out_path / "table_intake/table_manifest.jsonl"),
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
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-ruleset-review",
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
                    output_dir=temp_dir / "pv_domain_intake"
                )

                pv_ruleset_manifests.append(pv_t_manifest_jsonl)
                pv_ruleset_profiles.append(pv_t_profiles_jsonl)

                metric_rows, field_mapping, findings, summary = run_pv_domain_review(
                    manifest_path=pv_t_manifest_jsonl,
                    column_profiles_path=pv_t_profiles_jsonl,
                    output_dir=temp_dir / "pv_domain"
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

        # PV Ruleset Completeness Review
        rs_start = time.time()
        combined_manifest = temp_dir / "pv_ruleset_combined_manifest.jsonl"
        combined_profiles = temp_dir / "pv_ruleset_combined_profiles.jsonl"

        has_manifests = False
        with open(combined_manifest, "w", encoding="utf-8") as f_m, open(combined_profiles, "w", encoding="utf-8") as f_p:
            for m_path in pv_ruleset_manifests:
                m_path = Path(m_path)
                if m_path.exists():
                    has_manifests = True
                    with open(m_path, "r", encoding="utf-8") as f_in:
                        for line in f_in:
                            if line.strip():
                                f_m.write(line.strip() + "\n")
            for p_path in pv_ruleset_profiles:
                p_path = Path(p_path)
                if p_path.exists():
                    with open(p_path, "r", encoding="utf-8") as f_in:
                        for line in f_in:
                            if line.strip():
                                f_p.write(line.strip() + "\n")

        if has_manifests:
            try:
                from integrity_agent.workflows.pv_ruleset_review import run_pv_ruleset_review
                rs_findings, rs_summary, rs_pv_count = run_pv_ruleset_review(
                    input_path=combined_manifest,
                    column_profiles_path=combined_profiles,
                    output_dir=temp_dir / "pv_ruleset_review",
                    table_base_dir=pkg_input.package_dir
                )

                if rs_pv_count > 0:
                    safe_copy_file(rs_findings, out_path / "pv_ruleset_review/pv_ruleset_findings.jsonl")
                    safe_copy_file(rs_summary, out_path / "pv_ruleset_review/pv_ruleset_review_summary.md")

                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-ruleset-review",
                        status="success",
                        input_path=str(pkg_input.package_dir),
                        output_paths=[
                            str(out_path / "pv_ruleset_review/pv_ruleset_findings.jsonl"),
                            str(out_path / "pv_ruleset_review/pv_ruleset_review_summary.md")
                        ],
                        runtime_seconds=time.time() - rs_start
                    ))
                else:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-ruleset-review",
                        status="skipped",
                        warnings=["No tables with PV metadata detected."],
                        runtime_seconds=time.time() - rs_start
                    ))
            except Exception as rs_err:
                import traceback
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-ruleset-review",
                    status="failed",
                    input_path=str(pkg_input.package_dir),
                    error_message=str(rs_err) + "\n" + traceback.format_exc(),
                    runtime_seconds=time.time() - rs_start
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-ruleset-review",
                status="skipped",
                warnings=["No table or PV manifests available."],
                runtime_seconds=time.time() - rs_start
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
                    output_dir=temp_dir / "raw_pv"
                )

                # Copy all files from outputs/raw_pv to output_dir/raw_pv/
                safe_copy_file(temp_dir / "raw_pv/raw_pv_findings.jsonl", out_path / "raw_pv/raw_pv_findings.jsonl")
                safe_copy_file(temp_dir / "raw_pv/raw_pv_reconciliation_summary.md", out_path / "raw_pv/raw_pv_reconciliation_summary.md")
                safe_copy_file(temp_dir / "raw_pv/jv_metrics.jsonl", out_path / "raw_pv/jv_metrics.jsonl")
                safe_copy_file(temp_dir / "raw_pv/eqe_integration_results.jsonl", out_path / "raw_pv/eqe_integration_results.jsonl")
                safe_copy_file(temp_dir / "raw_pv/excel_formula_audit.jsonl", out_path / "raw_pv/excel_formula_audit.jsonl")

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
            out_path / "rule_findings.jsonl",
            temp_dir / "image_intake/image_findings.jsonl",
            temp_dir / "image_intake/image_similarity_candidates.jsonl",
            temp_dir / "table_intake/table_numeric_findings.jsonl",
            temp_dir / "pv_domain/pv_findings.jsonl",
            temp_dir / "raw_pv/raw_pv_findings.jsonl",
            temp_dir / "status_enrich/status_items.jsonl",
            temp_dir / "reference_scan/reference_anomalies.jsonl",
            temp_dir / "pv_ruleset_review/pv_ruleset_findings.jsonl"
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

                                # Apply package runner risk level cap:
                                # All findings have risk levels limited to low or medium
                                # (or high for retraction/withdrawal status contexts).
                                rl = d.get("risk_level", "low").lower()
                                if rl == "high":
                                    is_retraction = any(kw in rule_id.lower() for kw in ["retract", "withdraw"])
                                    if not is_retraction:
                                        d["risk_level"] = "medium"
                                        if "risk" in d:
                                            d["risk"] = "medium"
                                src = d.get("source_file") or d.get("relative_path") or d.get("relative_path_a")
                                if not src:
                                    ev_list = d.get("evidence_items") or d.get("evidence") or []
                                    if ev_list:
                                        src = ev_list[0].get("source") or ev_list[0].get("relative_path")
                                if not src:
                                    src = "unknown_file"

                                d["source_file"] = src
                                safe_lang = d.get("safe_report_language", "")
                                comp_key = (rule_id, src, str(safe_lang))

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
                output_path=str(dashboard_html_path),
                locale=locale,
            )
            module_statuses.append(EvidenceModuleStatus(
                module_name="report-review-package-html",
                status="success",
                input_path=str(unified_index_path),
                output_paths=[str(dashboard_html_path)],
                runtime_seconds=time.time() - dash_start
            ))
            if summary_md_path.exists():
                with open(summary_md_path, "a", encoding="utf-8") as f_summary:
                    f_summary.write(
                        "\n## Interactive Review Dashboard\n"
                        f"- A bilingual interactive web dashboard has been generated at: `{dashboard_html_path.name}`\n"
                    )
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

        from integrity_agent.core.risk_model import calculate_mrpi
        calculated_mrpi = calculate_mrpi(unified_findings)

        run_summary = ReviewPackageRunSummary(
            manifest=manifest,
            module_statuses=module_statuses,
            overall_status=overall_status,
            total_runtime_seconds=total_runtime,
            findings_summary=findings_summary,
            mrpi=calculated_mrpi,
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
        if dashboard_html_path.exists():
            print(f"Wrote interactive dashboard: {display_path(dashboard_html_path)}")
        print(f"Unified evidence review completed in {total_runtime:.2f}s with status {overall_status}.")
        return run_summary

    finally:
        try:
            temp_dir_obj.cleanup()
        except Exception:
            pass

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
