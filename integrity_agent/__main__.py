from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from integrity_agent.core.path_display import display_path
from integrity_agent.workflows.case_distill import CaseValidationError, run_case_distill
from integrity_agent.workflows.report_reader_review import write_reader_review_report
from integrity_agent.workflows.run_rules import run_rules


def _print_failed_review_modules(summary: object) -> None:
    from integrity_agent.core.safety import find_runtime_safety_issues

    for status in getattr(summary, "module_statuses", []) or []:
        if getattr(status, "status", None) != "failed":
            continue
        module_name = str(getattr(status, "module_name", "unknown-module"))
        skip_reason = str(getattr(status, "skip_reason", "") or "")
        detail = str(getattr(status, "error_message", "") or skip_reason or "failed")
        if find_runtime_safety_issues(detail):
            detail = skip_reason or "details withheld by runtime safety guard"
        print(f"ERROR: {module_name}: {detail}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="integrity-agent",
        description="Local research-integrity evidence review utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    case_parser = subparsers.add_parser(
        "case-distill",
        help="Convert a case note or YAML case card into a JSONL evidence ledger entry.",
    )
    case_parser.add_argument("input", type=Path, help="Markdown case note or YAML case card.")
    case_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs") / "evidence_ledger.jsonl",
        help="JSONL ledger output path.",
    )

    run_rules_parser = subparsers.add_parser(
        "run-rules",
        help="Run toy/stub detector rules against a local toy package.",
    )
    run_rules_parser.add_argument("package", type=Path, help="Toy rule package folder.")
    run_rules_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs") / "rule_findings.jsonl",
        help="Rule findings JSONL output path.",
    )
    run_rules_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network requests for metadata checks.",
    )

    report_parser = subparsers.add_parser(
        "report-reader-review",
        help="Build a reader review report from rule findings JSONL.",
    )
    report_parser.add_argument("findings", type=Path, help="Rule findings JSONL path.")
    report_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs") / "reader_review_report.md",
        help="Reader review report output path.",
    )

    validate_parser = subparsers.add_parser(
        "validate-ledger",
        help="Validate a JSONL evidence ledger contract, safety language, and path privacy.",
    )
    validate_parser.add_argument("input", type=Path, help="Evidence ledger JSONL path.")
    validate_parser.add_argument(
        "--schema-output",
        type=Path,
        help="Optional path to write the EvidenceRecord JSON Schema.",
    )

    intake_parser = subparsers.add_parser(
        "reader-intake",
        help="Run DOI normalizer, metadata client and update parser for a specific paper.",
    )
    intake_parser.add_argument("--doi", type=str, required=True, help="Raw DOI string to intake.")
    intake_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network requests to query Crossref API.",
    )

    batch_parser = subparsers.add_parser(
        "batch-intake",
        help="Run batch literature intake for bibliography files or DOI lists.",
    )
    batch_parser.add_argument("input", type=Path, help="Input file path (txt, csv, json, bib).")
    batch_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network requests to query Crossref API.",
    )
    batch_parser.add_argument(
        "--mailto",
        type=str,
        help="Email address for polite API usage.",
    )

    status_enrich_parser = subparsers.add_parser(
        "status-enrich",
        help="Enrich DOI status by querying Crossref metadata (offline stub by default).",
    )
    status_enrich_parser.add_argument("input", type=Path, help="Input file path (txt, csv, json, jsonl).")
    status_enrich_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network requests to query Crossref API.",
    )
    status_enrich_parser.add_argument(
        "--mailto",
        type=str,
        help="Email address for polite API usage.",
    )
    status_enrich_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs") / "status_enrich",
        help="Custom output directory path.",
    )

    reference_scan_parser = subparsers.add_parser(
        "reference-scan",
        help="Scan references and citations for metadata anomalies (offline stub by default).",
    )
    reference_scan_parser.add_argument("input", type=Path, help="Input file containing references/DOIs (JSONL or TXT).")
    reference_scan_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network requests to query Crossref API.",
    )
    reference_scan_parser.add_argument(
        "--mailto",
        type=str,
        help="Email address for polite API usage.",
    )
    reference_scan_parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs") / "reference_scan",
        help="Custom output directory path.",
    )

    claim_intake_parser = subparsers.add_parser(
        "document-claim-intake",
        help="Validate and normalize human-located atomic claims from claims.jsonl.",
    )
    claim_intake_parser.add_argument(
        "input",
        type=Path,
        help="Structured claims.jsonl path or its containing documents directory.",
    )
    claim_intake_parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs") / "document_claim_intake",
        help="Directory for normalized claims and the intake manifest.",
    )


    html_parser = subparsers.add_parser(
        "report-batch-html",
        help="Generate a static HTML review table from a batch items JSONL file.",
    )
    html_parser.add_argument("input", type=Path, help="Input JSONL file (batch_items.jsonl).")
    html_parser.add_argument("-o", "--output", type=Path, help="Optional custom output HTML file path.")

    pv_html_parser = subparsers.add_parser(
        "report-pv-domain-html",
        help="Generate a static HTML review dashboard from PV findings JSONL.",
    )
    pv_html_parser.add_argument("input", type=Path, help="Path to pv_findings.jsonl.")
    pv_html_parser.add_argument("-o", "--output", type=Path, help="Optional custom output HTML file path.")


    image_parser = subparsers.add_parser(
        "image-intake",
        help="Run image metadata folder intake and exact duplicate checks.",
    )
    image_parser.add_argument("input", type=Path, help="Input directory containing image files.")

    sheet_parser = subparsers.add_parser(
        "report-image-contact-sheet",
        help="Generate a static HTML contact sheet dashboard visualizing all images.",
    )
    sheet_parser.add_argument("input", type=Path, help="Input image manifest JSONL file.")
    sheet_parser.add_argument("-o", "--output", type=Path, help="Optional custom output HTML file path.")

    sim_parser = subparsers.add_parser(
        "image-similarity",
        help="Run perceptual similarity checks on an image manifest.",
    )
    sim_parser.add_argument("input", type=Path, help="Path to image_manifest.jsonl.")
    sim_parser.add_argument("--threshold", type=int, default=6, help="Hamming distance threshold (default: 6).")
    sim_parser.add_argument("--hash-method", type=str, default="dhash", choices=["dhash", "phash"], help="Perceptual hash algorithm to use.")

    pairs_parser = subparsers.add_parser(
        "report-image-similarity-pairs",
        help="Generate a static HTML contact sheet dashboard visualizing visual similarity candidate pairs.",
    )
    pairs_parser.add_argument("input", type=Path, help="Input image similarity candidates JSONL file.")
    pairs_parser.add_argument("-o", "--output", type=Path, help="Optional custom output HTML file path.")

    t_intake_parser = subparsers.add_parser(
        "table-intake",
        help="Run table source data folder intake and column profiling.",
    )
    t_intake_parser.add_argument("input", type=Path, help="Input directory containing source data table files.")
    t_intake_parser.add_argument("-o", "--output", type=Path, help="Optional custom output directory path.")

    t_review_parser = subparsers.add_parser(
        "table-numeric-review",
        help="Run numeric detectors on a table manifest.",
    )
    t_review_parser.add_argument("input", type=Path, help="Path to table_manifest.jsonl.")
    t_review_parser.add_argument("-o", "--output", type=Path, help="Optional custom output directory path.")
    t_review_parser.add_argument(
        "--column-profiles",
        type=Path,
        help="Optional path to table-intake column_profiles.jsonl.",
    )

    t_html_parser = subparsers.add_parser(
        "report-table-review-html",
        help="Generate a static HTML review dashboard from a table manifest.",
    )
    t_html_parser.add_argument("input", type=Path, help="Path to table_manifest.jsonl.")
    t_html_parser.add_argument("-o", "--output", type=Path, help="Optional custom output HTML file path.")

    pv_parser = subparsers.add_parser(
        "pv-domain-review",
        help="Run photovoltaics and materials domain consistency reviews on a table manifest.",
    )
    pv_parser.add_argument("input", type=Path, help="Path to table_manifest.jsonl.")
    pv_parser.add_argument("--column-profiles", type=Path, help="Path to column_profiles.jsonl.")
    pv_parser.add_argument("--output-dir", type=Path, help="Custom output directory path.")
    pv_parser.add_argument("--pce-tolerance-abs", type=float, default=0.3, help="Absolute tolerance for PCE.")
    pv_parser.add_argument("--pce-tolerance-rel", type=float, default=0.03, help="Relative tolerance for PCE.")
    pv_parser.add_argument("--eqe-jsc-tolerance-rel", type=float, default=0.10, help="Relative tolerance for EQE vs JV Jsc.")
    pv_parser.add_argument("--eqe-jsc-tolerance-abs", type=float, default=1.0, help="Absolute tolerance for EQE vs JV Jsc.")

    pv_ruleset_review_parser = subparsers.add_parser(
        "pv-ruleset-review",
        help="Run photovoltaics and materials evidence ruleset completeness review.",
    )
    pv_ruleset_review_parser.add_argument("input", type=Path, help="Path to table_manifest.jsonl or directory containing table files.")
    pv_ruleset_review_parser.add_argument("--column-profiles", type=Path, help="Optional path to column_profiles.jsonl.")
    pv_ruleset_review_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/pv_ruleset_review"), help="Optional custom output directory path.")

    # graph-export
    graph_export_parser = subparsers.add_parser(
        "graph-export",
        help="Export a provenance graph of nodes and edges from a unified evidence index.",
    )
    graph_export_parser.add_argument("input", type=Path, help="Path to unified_evidence_index.jsonl.")
    graph_export_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/graph_export"), help="Optional custom output directory path.")

    # init-package
    init_parser = subparsers.add_parser(
        "init-package",
        help="Initialize a local review package directory structure.",
    )
    init_parser.add_argument("package_dir", type=Path, help="Directory to initialize.")

    # run-audit
    run_audit_parser = subparsers.add_parser(
        "run-audit",
        help="Run comprehensive integrity audit on a local package.",
    )
    run_audit_parser.add_argument("package_dir", type=Path, help="Path to package directory.")
    run_audit_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/review_package"), help="Directory to write output files.")
    run_audit_parser.add_argument("--skip-images", action="store_true", help="Skip image analysis.")
    run_audit_parser.add_argument("--skip-tables", action="store_true", help="Skip table analysis.")
    run_audit_parser.add_argument("--skip-pv", action="store_true", help="Skip PV metadata checks.")
    run_audit_parser.add_argument("--skip-raw-pv", action="store_true", help="Skip raw PV reconciliation.")
    run_audit_parser.add_argument("--allow-network", action="store_true", help="Allow network requests for status-enrich and metadata retrieval.")

    # validate-report
    validate_report_parser = subparsers.add_parser(
        "validate-report",
        help="Validate a generated findings ledger file and check basic output presence.",
    )
    validate_report_parser.add_argument("findings_file", type=Path, help="Path to findings jsonl file.")


    # raw-pv-intake
    raw_intake_parser = subparsers.add_parser("raw-pv-intake", help="Scan and intake raw measurements package.")
    raw_intake_parser.add_argument("package_dir", type=Path, help="Path to raw measurements package directory.")
    raw_intake_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/raw_pv"), help="Directory for output files.")

    # jv-recalculate
    jv_recalc_parser = subparsers.add_parser("jv-recalculate", help="Recalculate metrics from raw J–V sweep files.")
    jv_recalc_parser.add_argument("jv_folder", type=Path, help="Directory containing J–V sweep files.")
    jv_recalc_parser.add_argument("--reported", type=Path, help="Reported metrics CSV file.")
    jv_recalc_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/raw_pv"), help="Directory for output files.")
    jv_recalc_parser.add_argument("--pin", type=float, default=100.0, help="Light intensity in mW/cm2.")

    # eqe-recalculate
    eqe_recalc_parser = subparsers.add_parser("eqe-recalculate", help="Recalculate EQE integrated current density.")
    eqe_recalc_parser.add_argument("eqe_folder", type=Path, help="Directory containing EQE spectrum files.")
    eqe_recalc_parser.add_argument("--reference", type=Path, help="Path to reference AM1.5G spectrum file.")
    eqe_recalc_parser.add_argument("--reported", type=Path, help="Reported metrics CSV file.")
    eqe_recalc_parser.add_argument("--jv-metrics", type=Path, help="Path to compiled J–V metrics jsonl.")
    eqe_recalc_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/raw_pv"), help="Directory for output files.")

    # excel-formula-audit
    excel_audit_parser = subparsers.add_parser("excel-formula-audit", help="Audit Excel spreadsheets for formula and hardcoding.")
    excel_audit_parser.add_argument("excel_folder", type=Path, help="Directory containing Excel spreadsheet files.")
    excel_audit_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/raw_pv"), help="Directory for output files.")

    # raw-pv-reconcile
    reconcile_parser = subparsers.add_parser("raw-pv-reconcile", help="Coordinated raw measurement reconciliation workflow.")
    reconcile_parser.add_argument("package_dir", type=Path, help="Path to raw measurements package directory.")
    reconcile_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/raw_pv"), help="Directory for output files.")

    # report-raw-pv-html
    raw_html_parser = subparsers.add_parser("report-raw-pv-html", help="Generate a static HTML review dashboard from raw PV findings JSONL.")
    raw_html_parser.add_argument("input", type=Path, help="Path to raw_pv_findings.jsonl.")
    raw_html_parser.add_argument("-o", "--output", type=Path, default=Path("outputs/raw_pv/raw_pv_dashboard.html"), help="Path to write dashboard HTML.")

    # geng-video-index
    gv_index_parser = subparsers.add_parser("geng-video-index", help="Build a safe public index for Geng Bilibili dry-run videos.")
    gv_index_parser.add_argument("seed_urls", type=Path, help="Private seed URL list. Created with defaults if missing.")
    gv_index_parser.add_argument("--output", type=Path, default=Path("outputs/geng_video_distillation/geng_video_index.yml"), help="Video index output path. Defaults to outputs/ to avoid generated artifacts in knowledge_base.")
    gv_index_parser.add_argument("--private-root", type=Path, default=Path("private_video_corpora/geng_bilibili"), help="Private Bilibili corpus root.")
    gv_index_parser.add_argument("--metadata-mode", choices=["live", "fixture"], default="fixture", help="Use synthetic fixture metadata by default; live Bilibili API metadata requires --allow-network.")
    gv_index_parser.add_argument("--allow-network", action="store_true", help="Permit live Bilibili metadata requests when --metadata-mode live is selected.")
    gv_index_parser.add_argument("--write-private-cache", action="store_true", help="Opt in to writing non-fixture live metadata/subtitle cache under --private-root. Fixture mode never writes transcript/raw-metadata cache.")

    # geng-video-distill
    gv_distill_parser = subparsers.add_parser("geng-video-distill", help="Dry-run distill indexed Geng videos into safe public case cards.")
    gv_distill_parser.add_argument("index", type=Path, help="Path to geng_video_index.yml.")
    gv_distill_parser.add_argument("--dry-run", type=int, default=3, help="Number of indexed videos to process.")
    gv_distill_parser.add_argument("--output-dir", type=Path, default=Path("outputs/geng_video_distillation/cases"), help="Case card output directory. Defaults to outputs/ to keep generated artifacts out of knowledge_base.")
    gv_distill_parser.add_argument("--private-root", type=Path, default=Path("private_video_corpora/geng_bilibili"), help="Private Bilibili corpus root.")

    # geng-video-safety-check / geng-video-verify
    gv_safety_parser = subparsers.add_parser("geng-video-safety-check", help="Validate public Geng Bilibili case cards for safety boundaries.")
    gv_safety_parser.add_argument("case_dir", type=Path, help="Directory of public Geng video case cards.")
    gv_verify_parser = subparsers.add_parser("geng-video-verify", help="Alias for geng-video-safety-check; validates public Geng case-card safety boundaries.")
    gv_verify_parser.add_argument("case_dir", type=Path, help="Directory of public Geng video case cards.")

    # geng-video-rule-candidates
    gv_rules_parser = subparsers.add_parser("geng-video-rule-candidates", help="Generate detector rule candidate drafts from Geng video case cards.")
    gv_rules_parser.add_argument("case_dir", type=Path, help="Directory of public Geng video case cards.")
    gv_rules_parser.add_argument("--output-dir", type=Path, default=Path("outputs/geng_video_distillation/rule_candidates"), help="Detector candidate output directory. Defaults to outputs/ to keep generated artifacts out of knowledge_base.")

    # review-package
    rev_pkg_parser = subparsers.add_parser("review-package", help="Run paper/package-level evidence review.")
    rev_pkg_parser.add_argument("package_dir", type=Path, help="Path to package directory (e.g. examples/toy_review_package).")
    rev_pkg_parser.add_argument("--skip-images", action="store_true", help="Skip image intake and similarity modules.")
    rev_pkg_parser.add_argument("--skip-tables", action="store_true", help="Skip table intake and numeric reviews.")
    rev_pkg_parser.add_argument("--skip-pv", action="store_true", help="Skip PV domain review module.")
    rev_pkg_parser.add_argument("--skip-raw-pv", action="store_true", help="Skip raw PV recalculation module.")
    rev_pkg_parser.add_argument("--allow-network", action="store_true", help="Allow network requests for metadata checks.")
    rev_pkg_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/review_package"), help="Directory to write output files.")
    rev_pkg_parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Dashboard language.")
    rev_pkg_parser.add_argument("--view", action="store_true", help="Open the generated local dashboard in a browser.")

    # report-review-package-html
    rev_html_parser = subparsers.add_parser("report-review-package-html", help="Generate a static HTML review dashboard from unified findings.")
    rev_html_parser.add_argument("unified_index", type=Path, help="Path to unified_evidence_index.jsonl.")
    rev_html_parser.add_argument("-o", "--output", type=Path, default=Path("outputs/review_package/review_package_dashboard.html"), help="Path to write dashboard HTML.")
    rev_html_parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Dashboard language.")
    rev_html_parser.add_argument("--view", action="store_true", help="Open the generated local dashboard in a browser.")

    view_parser = subparsers.add_parser("view", help="Serve an existing local report folder and open it in a browser.")
    view_parser.add_argument("output_dir", type=Path, help="Folder containing a generated HTML report.")
    view_parser.add_argument("--report-name", type=str, help="Specific HTML report file to open.")
    view_parser.add_argument("--port", type=int, default=8080, help="Preferred local port.")
    view_parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Viewer message language.")

    wizard_parser = subparsers.add_parser("wizard", help="Guided bilingual setup for reviewing a local paper package.")
    wizard_parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Wizard language.")
    wizard_parser.add_argument("--package-dir", type=Path, help="Directory containing paper materials.")
    wizard_parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs/review_package"), help="Directory to write output files.")
    wizard_parser.add_argument("--dry-run", action="store_true", help="Preview the wizard plan without running detectors.")
    wizard_parser.add_argument("--view", action="store_true", help="Open the generated local dashboard after a successful run.")
    # pv-ruleset-export
    ruleset_export_parser = subparsers.add_parser(
        "pv-ruleset-export",
        help="Export the Photovoltaics (PV) Evidence Ruleset v1 taxonomy to JSON and Markdown.",
    )
    ruleset_export_parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Optional custom output directory path (defaults to outputs/pv_ruleset_v1).",
    )

    return parser



def _run_wizard(args: argparse.Namespace) -> int:
    from integrity_agent.core.i18n import I18nManager

    manager = I18nManager()
    manager.set_locale(args.lang)
    print(manager.translate("wizard.title"))
    print(manager.translate("wizard.no_upload"))

    package_dir = args.package_dir
    if package_dir is None:
        raw = input(f"{manager.translate('wizard.package_dir')}: ").strip()
        package_dir = Path(raw)

    print(f"{manager.translate('wizard.will_analyze')}: {display_path(package_dir)}")
    print(f"{manager.translate('wizard.output_dir')}: {display_path(args.output_dir)}")

    metadata_exists = (package_dir / "metadata").is_dir()
    images_exists = (package_dir / "images").is_dir()
    tables_exists = (package_dir / "tables").is_dir()
    pv_exists = (package_dir / "pv").is_dir()
    raw_pv_exists = (package_dir / "raw_pv").is_dir()

    if args.dry_run:
        print(f"\n{manager.translate('wizard.detected_subdirs')}:")
        status_metadata = manager.translate('wizard.detected') if metadata_exists else manager.translate('wizard.not_detected')
        status_images = manager.translate('wizard.detected') if images_exists else manager.translate('wizard.not_detected')
        status_tables = manager.translate('wizard.detected') if tables_exists else manager.translate('wizard.not_detected')
        status_pv = manager.translate('wizard.detected') if pv_exists else manager.translate('wizard.not_detected')
        status_raw_pv = manager.translate('wizard.detected') if raw_pv_exists else manager.translate('wizard.not_detected')

        print(f"  - metadata: {status_metadata}")
        print(f"  - images: {status_images}")
        print(f"  - tables: {status_tables}")
        print(f"  - pv: {status_pv}")
        print(f"  - raw_pv: {status_raw_pv}")

        print(f"\n{manager.translate('wizard.module_plan')}:")
        has_doi = (package_dir / "metadata" / "doi.txt").exists()
        run_reader = manager.translate('wizard.will_run') if (metadata_exists and has_doi) else manager.translate('wizard.will_skip')
        run_images = manager.translate('wizard.will_run') if images_exists else manager.translate('wizard.will_skip')
        run_tables = manager.translate('wizard.will_run') if tables_exists else manager.translate('wizard.will_skip')
        run_pv = manager.translate('wizard.will_run') if pv_exists else manager.translate('wizard.will_skip')
        run_raw_pv = manager.translate('wizard.will_run') if raw_pv_exists else manager.translate('wizard.will_skip')

        print(f"  - reader-intake: {run_reader}")
        print(f"  - image-intake: {run_images}")
        print(f"  - image-similarity: {run_images}")
        print(f"  - table-intake: {run_tables}")
        print(f"  - table-numeric-review: {run_tables}")
        print(f"  - pv-domain-review: {run_pv}")
        print(f"  - raw-pv-reconcile: {run_raw_pv}")

        print(f"\n{manager.translate('wizard.local_info')}")
        print(manager.translate("wizard.dry_run"))
        return 0

    from integrity_agent.workflows.review_package import run_review_package

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(args.output_dir),
        locale=args.lang,
    )
    if summary.overall_status == "failed":
        _print_failed_review_modules(summary)
        print("ERROR: review package completed with failed modules.", file=sys.stderr)
        return 2
    print(f"{manager.translate('wizard.next_step')}: integrity-agent view {display_path(args.output_dir)}")

    if args.view:
        from integrity_agent.workflows.report_viewer import start_server_and_open_browser

        viewer = start_server_and_open_browser(
            args.output_dir,
            report_name="review_package_dashboard.html",
            locale=args.lang,
        )
        try:
            input("Press Enter to stop the local report server...")
        finally:
            viewer.shutdown()
    return 0



def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "case-distill":
        try:
            output_path = run_case_distill(
                args.input,
                args.output,
                emit_warning=lambda msg: print(f"WARNING: {msg}", file=sys.stderr),
            )
        except CaseValidationError as exc:
            for warning in exc.warnings:
                print(f"WARNING: {warning}", file=sys.stderr)
            for error in exc.errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        print(f"Wrote evidence ledger: {display_path(output_path)}")
        return 0

    if args.command == "run-rules":
        output_path = run_rules(args.package, args.output, allow_network=args.allow_network)
        print(f"Wrote rule findings: {display_path(output_path)}")
        return 0

    if args.command == "report-reader-review":
        output_path = write_reader_review_report(args.findings, args.output)
        print(f"Wrote reader review report: {display_path(output_path)}")
        return 0

    if args.command == "validate-ledger":
        from integrity_agent.workflows.validate_ledger import (
            validate_ledger_file,
            write_ledger_json_schema,
        )

        if args.schema_output:
            schema_path = write_ledger_json_schema(args.schema_output)
            print(f"Wrote ledger JSON Schema: {display_path(schema_path)}")
        result = validate_ledger_file(args.input)
        if not result.ok:
            for issue in result.issues:
                print(f"ERROR: {issue.format()}", file=sys.stderr)
            return 2
        print(f"Ledger validation passed: records={result.records}")
        return 0

    if args.command == "reader-intake":
        from integrity_agent.workflows.reader_intake import run_reader_intake
        meta_path, summary_path = run_reader_intake(args.doi, allow_network=args.allow_network)
        print(f"Wrote metadata: {display_path(meta_path)}")
        print(f"Wrote summary: {display_path(summary_path)}")
        return 0

    if args.command == "document-claim-intake":
        from integrity_agent.workflows.document_claim_intake import (
            DocumentClaimIntakeError,
            run_document_claim_intake,
        )

        try:
            claims_path, manifest_path = run_document_claim_intake(
                args.input,
                output_dir=args.output_dir,
            )
        except DocumentClaimIntakeError as exc:
            for issue in exc.issues:
                print(f"ERROR: {issue}", file=sys.stderr)
            return 2
        print(f"Wrote normalized document claims: {display_path(claims_path)}")
        print(f"Wrote document claim intake manifest: {display_path(manifest_path)}")
        return 0

    if args.command == "batch-intake":
        from integrity_agent.workflows.batch_intake import run_batch_intake
        jsonl_path, csv_path, summary_path = run_batch_intake(
            args.input,
            allow_network=args.allow_network,
            mailto=args.mailto
        )
        print(f"Wrote batch JSONL: {display_path(jsonl_path)}")
        print(f"Wrote batch CSV table: {display_path(csv_path)}")
        print(f"Wrote batch summary: {display_path(summary_path)}")
        return 0

    if args.command == "status-enrich":
        from integrity_agent.workflows.status_enrich import run_status_enrich
        jsonl_path, summary_path = run_status_enrich(
            args.input,
            allow_network=args.allow_network,
            mailto=args.mailto,
            output_dir=args.output_dir,
        )
        print(f"Wrote status JSONL: {display_path(jsonl_path)}")
        print(f"Wrote status summary: {display_path(summary_path)}")
        return 0

    if args.command == "reference-scan":
        from integrity_agent.workflows.reference_scan import run_reference_scan
        jsonl_path, summary_path = run_reference_scan(
            args.input,
            allow_network=args.allow_network,
            mailto=args.mailto,
            output_dir=args.output_dir,
        )
        print(f"Wrote reference anomalies JSONL: {display_path(jsonl_path)}")
        print(f"Wrote reference anomalies summary: {display_path(summary_path)}")
        return 0


    if args.command == "image-intake":
        from integrity_agent.workflows.image_intake import run_image_intake
        manifest_jsonl, manifest_csv, findings_jsonl, summary_md = run_image_intake(args.input)
        print(f"Wrote image manifest JSONL: {display_path(manifest_jsonl)}")
        print(f"Wrote image manifest CSV: {display_path(manifest_csv)}")
        print(f"Wrote image findings: {display_path(findings_jsonl)}")
        print(f"Wrote image summary: {display_path(summary_md)}")
        return 0

    if args.command == "report-batch-html":
        from integrity_agent.workflows.report_batch_html import generate_batch_html
        html_path = generate_batch_html(args.input, output_path=args.output)
        print(f"Wrote batch HTML review table: {display_path(html_path)}")
        return 0

    if args.command == "report-pv-domain-html":
        from integrity_agent.workflows.report_pv_domain_html import generate_pv_domain_html
        html_path = generate_pv_domain_html(args.input, output_path=args.output)
        print(f"Wrote PV domain dashboard HTML: {display_path(html_path)}")
        return 0


    if args.command == "report-image-contact-sheet":
        from integrity_agent.workflows.report_image_contact_sheet import generate_image_contact_sheet
        sheet_path = generate_image_contact_sheet(args.input, output_path=args.output)
        print(f"Wrote image contact sheet HTML: {display_path(sheet_path)}")
        return 0

    if args.command == "image-similarity":
        from integrity_agent.workflows.image_similarity import run_image_similarity
        hashes_path, candidates_path, summary_path = run_image_similarity(
            args.input,
            threshold=args.threshold,
            hash_method=args.hash_method
        )
        print(f"Wrote image hashes JSONL: {display_path(hashes_path)}")
        print(f"Wrote similarity candidates JSONL: {display_path(candidates_path)}")
        print(f"Wrote similarity summary MD: {display_path(summary_path)}")
        return 0

    if args.command == "report-image-similarity-pairs":
        from integrity_agent.workflows.report_image_similarity_pairs import generate_similarity_pairs_html
        pairs_path = generate_similarity_pairs_html(args.input, output_path=args.output)
        print(f"Wrote image similarity pairs HTML: {display_path(pairs_path)}")
        return 0

    if args.command == "table-intake":
        from integrity_agent.workflows.table_intake import run_table_intake
        manifest_jsonl, manifest_csv, profiles_jsonl, summary_md = run_table_intake(
            args.input,
            output_dir=args.output
        )
        print(f"Wrote table manifest JSONL: {display_path(manifest_jsonl)}")
        print(f"Wrote table manifest CSV: {display_path(manifest_csv)}")
        print(f"Wrote column profiles: {display_path(profiles_jsonl)}")
        print(f"Wrote table summary: {display_path(summary_md)}")
        return 0

    if args.command == "table-numeric-review":
        from integrity_agent.workflows.table_numeric_review import run_table_numeric_review
        findings_jsonl, summary_md = run_table_numeric_review(
            args.input,
            output_dir=args.output,
            column_profiles_path=args.column_profiles,
        )
        print(f"Wrote table numeric findings: {display_path(findings_jsonl)}")
        print(f"Wrote table numeric summary: {display_path(summary_md)}")
        return 0

    if args.command == "report-table-review-html":
        from integrity_agent.workflows.report_table_review_html import generate_table_review_html
        dashboard_path = generate_table_review_html(
            args.input,
            output_path=args.output
        )
        print(f"Wrote table review dashboard HTML: {display_path(dashboard_path)}")
        return 0

    if args.command == "pv-domain-review":
        from integrity_agent.workflows.pv_domain_review import run_pv_domain_review
        metric_rows, field_mapping, findings, summary = run_pv_domain_review(
            args.input,
            column_profiles_path=args.column_profiles,
            output_dir=args.output_dir,
            pce_tolerance_abs=args.pce_tolerance_abs,
            pce_tolerance_rel=args.pce_tolerance_rel,
            eqe_jsc_tolerance_rel=args.eqe_jsc_tolerance_rel,
            eqe_jsc_tolerance_abs=args.eqe_jsc_tolerance_abs
        )
        print(f"Wrote PV metric rows: {display_path(metric_rows)}")
        print(f"Wrote PV field mappings: {display_path(field_mapping)}")
        print(f"Wrote PV findings: {display_path(findings)}")
        print(f"Wrote PV domain summary: {display_path(summary)}")
        return 0

    if args.command == "pv-ruleset-review":
        from integrity_agent.workflows.pv_ruleset_review import run_pv_ruleset_review
        findings, summary, _ = run_pv_ruleset_review(
            args.input,
            column_profiles_path=args.column_profiles,
            output_dir=args.output_dir,
        )
        return 0

    if args.command == "graph-export":
        from integrity_agent.workflows.graph_export import run_graph_export
        run_graph_export(
            args.input,
            output_dir=args.output_dir,
        )
        return 0

    if args.command == "init-package":
        from integrity_agent.workflows.package_scaffold import (
            initialize_review_package,
        )

        pkg_dir = Path(args.package_dir)
        initialize_review_package(pkg_dir)
        print(f"Initialized local review package structure at: {display_path(pkg_dir)}")
        print("Start with PACKAGE_GUIDE.md, then confirm only the templates you need.")
        print("Safety & Privacy Notice:")
        print("- All analysis is local-first. Source data is not uploaded to external services.")
        print("- Findings are risk signals only and do not prove research misconduct.")
        return 0

    if args.command == "run-audit":
        from integrity_agent.workflows.review_package import run_review_package
        summary = run_review_package(
            package_dir=str(args.package_dir),
            skip_images=args.skip_images,
            skip_tables=args.skip_tables,
            skip_pv=args.skip_pv,
            skip_raw_pv=args.skip_raw_pv,
            allow_network=args.allow_network,
            output_dir=str(args.output_dir),
        )
        print("Audit run complete.")
        print(f"Unified evidence index: {display_path(Path(args.output_dir) / 'unified_evidence_index.jsonl')}")
        print("Notice: Signals are advisory risk markers for manual review, not misconduct proof.")
        if summary.overall_status == "failed":
            _print_failed_review_modules(summary)
            print("ERROR: audit modules or final ledger validation failed.", file=sys.stderr)
            return 2
        return 0

    if args.command == "validate-report":
        from integrity_agent.workflows.validate_ledger import validate_ledger_file
        findings_path = Path(args.findings_file)
        if not findings_path.exists():
            print(f"Error: Findings file not found: {findings_path}")
            return 1

        validation_res = validate_ledger_file(findings_path)
        print("Ledger Schema Validation Results:")
        if validation_res.issues:
            print(f"FAILED: Found {len(validation_res.issues)} issue(s):")
            for issue in validation_res.issues:
                print(f"- {issue}")
        else:
            print("PASSED: Schema validation matches all constraints.")

        # Basic artifact presence check
        parent = findings_path.parent
        summary_md = parent / "pv_ruleset_review_summary.md"
        pkg_summary_md = parent / "review_package_summary.md"
        print("\nArtifact Presence Checks:")
        checked_any = False
        if summary_md.exists():
            print(f"- Found PV ruleset summary: {display_path(summary_md)}")
            checked_any = True
        if pkg_summary_md.exists():
            print(f"- Found package summary: {display_path(pkg_summary_md)}")
            checked_any = True
        if not checked_any:
            print("- No optional summary Markdown found in the same folder.")

        print("\nDisclaimer:")
        print("- Validating a ledger does not confirm the truth or correctness of the findings.")
        print("- Generated findings are advisory completeness/consistency signals requiring manual review.")
        return 0 if not validation_res.issues else 1


    if args.command == "raw-pv-intake":
        from integrity_agent.workflows.raw_pv_intake import run_raw_pv_intake
        manifest, summary = run_raw_pv_intake(str(args.package_dir), str(args.output_dir))
        return 0

    if args.command == "jv-recalculate":
        from integrity_agent.workflows.jv_recalculate import run_jv_recalculate
        reported = str(args.reported) if args.reported else None
        run_jv_recalculate(str(args.jv_folder), reported, str(args.output_dir), args.pin)
        return 0

    if args.command == "eqe-recalculate":
        from integrity_agent.workflows.eqe_recalculate import run_eqe_recalculate
        reference = str(args.reference) if args.reference else None
        reported = str(args.reported) if args.reported else None
        jv_metrics = str(args.jv_metrics) if args.jv_metrics else None
        run_eqe_recalculate(str(args.eqe_folder), reference, reported, jv_metrics, str(args.output_dir))
        return 0

    if args.command == "excel-formula-audit":
        from integrity_agent.workflows.excel_formula_audit import run_excel_formula_audit
        run_excel_formula_audit(str(args.excel_folder), str(args.output_dir))
        return 0

    if args.command == "raw-pv-reconcile":
        from integrity_agent.workflows.raw_pv_reconciliation import run_raw_pv_reconciliation
        run_raw_pv_reconciliation(str(args.package_dir), str(args.output_dir))
        return 0

    if args.command == "report-raw-pv-html":
        from integrity_agent.workflows.report_raw_pv_html import run_report_raw_pv_html
        run_report_raw_pv_html(str(args.input), str(args.output))
        return 0

    if args.command == "geng-video-index":
        from integrity_agent.workflows.geng_video_distillation import (
            build_geng_video_index,
            fixture_metadata_fetcher,
        )
        fetcher = fixture_metadata_fetcher if args.metadata_mode == "fixture" else None
        if args.metadata_mode == "live" and not args.allow_network:
            parser.error("geng-video-index --metadata-mode live requires --allow-network")
        index_path = build_geng_video_index(
            args.seed_urls,
            index_path=args.output,
            private_root=args.private_root,
            fetcher=fetcher,
            write_private_cache=args.write_private_cache,
        )
        print(f"Wrote geng video index: {display_path(index_path)}")
        return 0

    if args.command == "geng-video-distill":
        from integrity_agent.workflows.geng_video_distillation import distill_geng_video_cases
        case_paths = distill_geng_video_cases(
            args.index,
            output_dir=args.output_dir,
            private_root=args.private_root,
            dry_run=args.dry_run,
        )
        print(f"Wrote geng video case cards: {len(case_paths)}")
        for path in case_paths:
            print(display_path(path))
        return 0

    if args.command in {"geng-video-safety-check", "geng-video-verify"}:
        from integrity_agent.workflows.geng_video_distillation import safety_check_geng_video_cases
        errors = safety_check_geng_video_cases(args.case_dir)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        print(f"Safety check passed: {display_path(args.case_dir)}")
        return 0

    if args.command == "geng-video-rule-candidates":
        from integrity_agent.workflows.geng_video_distillation import generate_geng_video_rule_candidates
        paths = generate_geng_video_rule_candidates(args.case_dir, output_dir=args.output_dir)
        print(f"Wrote geng video rule candidates: {len(paths)}")
        for path in paths:
            print(display_path(path))
        return 0

    if args.command == "review-package":
        from integrity_agent.workflows.review_package import run_review_package
        summary = run_review_package(
            package_dir=str(args.package_dir),
            skip_images=args.skip_images,
            skip_tables=args.skip_tables,
            skip_pv=args.skip_pv,
            skip_raw_pv=args.skip_raw_pv,
            allow_network=args.allow_network,
            output_dir=str(args.output_dir),
            locale=args.lang,
        )
        if summary.overall_status == "failed":
            _print_failed_review_modules(summary)
            print(
                "ERROR: review-package modules or final ledger validation failed.",
                file=sys.stderr,
            )
            return 2
        if args.view:
            from integrity_agent.workflows.report_viewer import start_server_and_open_browser
            viewer = start_server_and_open_browser(
                args.output_dir,
                report_name="review_package_dashboard.html",
                locale=args.lang,
            )
            try:
                input("Press Enter to stop the local report server...")
            finally:
                viewer.shutdown()
        return 0

    if args.command == "report-review-package-html":
        from integrity_agent.workflows.report_review_package_html import run_report_review_package_html
        run_report_review_package_html(
            unified_index=str(args.unified_index),
            output_path=str(args.output),
            locale=args.lang,
        )
        if args.view:
            from integrity_agent.workflows.report_viewer import start_server_and_open_browser
            viewer = start_server_and_open_browser(
                args.output.parent,
                report_name=args.output.name,
                locale=args.lang,
            )
            try:
                input("Press Enter to stop the local report server...")
            finally:
                viewer.shutdown()
        return 0

    if args.command == "view":
        from integrity_agent.workflows.report_viewer import start_server_and_open_browser
        viewer = start_server_and_open_browser(
            args.output_dir,
            port=args.port,
            report_name=args.report_name,
            locale=args.lang,
        )
        try:
            input("Press Enter to stop the local report server...")
        finally:
            viewer.shutdown()
        return 0

    if args.command == "wizard":
        return _run_wizard(args)

    if args.command == "pv-ruleset-export":
        from integrity_agent.workflows.pv_ruleset_export import run_pv_ruleset_export
        run_pv_ruleset_export(args.output_dir)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2



if __name__ == "__main__":
    raise SystemExit(main())
