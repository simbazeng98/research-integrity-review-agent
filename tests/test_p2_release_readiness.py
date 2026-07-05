from __future__ import annotations

import importlib
import subprocess
import sys
import warnings
from pathlib import Path

import yaml

from integrity_agent.__main__ import build_parser
from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.workflows.geng_video_distillation import RULE_CANDIDATE_LIBRARY
from integrity_agent.core.images.perceptual_hash import compute_dhash, compute_phash_fallback
from integrity_agent.core.safety import scan_for_forbidden_phrases


REQUIRED_RELEASE_COMMANDS = [
    "run-rules",
    "reader-intake",
    "batch-intake",
    "report-batch-html",
    "image-intake",
    "image-similarity",
    "report-image-contact-sheet",
    "report-image-similarity-pairs",
    "table-intake",
    "table-numeric-review",
    "report-table-review-html",
    "pv-domain-review",
    "report-pv-domain-html",
    "raw-pv-intake",
    "jv-recalculate",
    "eqe-recalculate",
    "excel-formula-audit",
    "raw-pv-reconcile",
    "report-raw-pv-html",
    "review-package",
    "report-review-package-html",
    "geng-video-index",
    "geng-video-distill",
    "geng-video-verify",
    "geng-video-safety-check",
    "geng-video-rule-candidates",
]
ALLOW_NETWORK_COMMANDS = {"run-rules", "reader-intake", "batch-intake", "review-package", "geng-video-index"}
REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def _ensure_rule_findings() -> Path:
    _run_cli(["run-rules", "examples/toy_rule_package"])
    findings = REPO_ROOT / "outputs" / "rule_findings.jsonl"
    assert findings.exists()
    return findings


def _ensure_reader_review_report() -> Path:
    _ensure_rule_findings()
    _run_cli(["report-reader-review", "outputs/rule_findings.jsonl"])
    report = REPO_ROOT / "outputs" / "reader_review_report.md"
    assert report.exists()
    return report


def _ensure_review_package_summary() -> Path:
    _run_cli(["review-package", "examples/toy_review_package"])
    summary = REPO_ROOT / "outputs" / "review_package" / "review_package_summary.md"
    assert summary.exists()
    return summary


def _safe_geng_card(detector_candidates: list[str]) -> dict[str, object]:
    return {
        "case_id": "case_cli_legacy",
        "source_type": "bilibili_video",
        "source_url": "https://www.bilibili.com/video/BVcase/",
        "bv_id": "BVcase",
        "video_title": "synthetic",
        "transcript_confidence": "synthetic_fixture",
        "case_kind": "methodology_distillation_from_geng_video",
        "method_source_case_kind": "methodology_note",
        "field": "research_integrity_methodology",
        "paper_identifiers": [],
        "public_status": "methodology_only",
        "public_status_basis": "Methodology-only fixture.",
        "video_raised_risk_signals": ["candidate method pattern only"],
        "evidence_patterns": ["verification_workflow"],
        "detector_candidates": detector_candidates,
        "methodology_reuse_scope": ["extract repeatable checking pattern"],
        "excluded_scope": ["paper-specific outcome"],
        "manual_verification_needed": ["raw data only if later applied"],
        "false_positive_risks": ["benign controls may trigger similar signals"],
        "safe_report_language": "Candidate method pattern requiring independent verification.",
        "limitations": ["not independently verified"],
        "private_notes_reference": "local_private_note_available_not_public",
    }


def test_cli_reference_covers_release_commands_and_network_scope():
    parser = build_parser()
    subcommands = parser._subparsers._group_actions[0].choices
    cli_reference = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    missing = [command for command in REQUIRED_RELEASE_COMMANDS if command not in subcommands or command not in cli_reference]
    assert missing == []

    for command in REQUIRED_RELEASE_COMMANDS:
        option_strings = set(subcommands[command]._option_string_actions)
        if command in ALLOW_NETWORK_COMMANDS:
            assert "--allow-network" in option_strings
        else:
            assert "--allow-network" not in option_strings


def test_no_public_video_claim_status_tracker_generated_even_from_legacy_cards(tmp_path):
    case_dir = tmp_path / "cases"
    out_dir = tmp_path / "rules"
    case_dir.mkdir()
    card = _safe_geng_card([
        "public_video_claim_status_tracker",
        "methodology_triage_workflow_from_geng_videos",
    ])
    (case_dir / "legacy_case.yml").write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "geng-video-rule-candidates", str(case_dir), "--output-dir", str(out_dir)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "public_video_claim_status_tracker" not in RULE_CANDIDATE_LIBRARY
    assert not list(out_dir.glob("*public_video_claim_status_tracker*.yml"))
    assert (out_dir / "methodology_triage_workflow_from_geng_videos.yml").exists()


def test_cli_has_release_ready_geng_video_defaults_and_verify_alias():
    parser = build_parser()
    subcommands = parser._subparsers._group_actions[0].choices  # argparse public-ish parser state
    assert "geng-video-verify" in subcommands

    index_args = parser.parse_args(["geng-video-index", "private_video_corpora/geng_bilibili/seed_urls.txt"])
    assert index_args.metadata_mode == "fixture"
    assert index_args.output.as_posix() == "outputs/geng_video_distillation/geng_video_index.yml"
    assert index_args.write_private_cache is False

    distill_args = parser.parse_args(["geng-video-distill", "outputs/geng_video_distillation/geng_video_index.yml"])
    assert distill_args.output_dir.as_posix() == "outputs/geng_video_distillation/cases"

    rules_args = parser.parse_args(["geng-video-rule-candidates", "outputs/geng_video_distillation/cases"])
    assert rules_args.output_dir.as_posix() == "outputs/geng_video_distillation/rule_candidates"


def test_docs_and_public_outputs_do_not_contain_forbidden_verdict_phrases():
    roots = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs",
        REPO_ROOT / "knowledge_base" / "cases",
        REPO_ROOT / "knowledge_base" / "detector_rules",
        REPO_ROOT / "knowledge_base" / "detector_rule_candidates",
        REPO_ROOT / "outputs",
    ]
    hits = []
    for root in roots:
        if root.exists():
            hits.extend(scan_for_forbidden_phrases(root, allow_test_negative_assertions=True))
    assert hits == []


def test_generated_outputs_do_not_leak_absolute_or_private_paths():
    generated_roots = [REPO_ROOT / "outputs"]
    forbidden_fragments = [
        "X:/PrivateProject",
        "X:\\PrivateProject",
        "C:/Users/private-user",
        "C:\\Users\\private-user",
        "private_video_corpora",
        "private_transcripts",
        "raw_metadata",
        "private_chunk_notes",
        "danmaku",
        "bullet_comments",
    ]
    hits: list[tuple[str, str]] = []
    for root in generated_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".html", ".jsonl", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for fragment in forbidden_fragments:
                if fragment in text:
                    hits.append((path.relative_to(REPO_ROOT).as_posix(), fragment))
    assert hits == []


def test_public_geng_video_titles_are_redacted_for_release():
    forbidden_title_terms = ["造假", "学术不端", "fraud", "misconduct", "guilty"]
    paths = list((REPO_ROOT / "knowledge_base" / "cases" / "geng_video_cases").glob("*.yml"))
    index_path = REPO_ROOT / "knowledge_base" / "video_index" / "geng_video_index.yml"
    if index_path.exists():
        paths.append(index_path)
    hits: list[str] = []
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        records = data.get("videos") if isinstance(data, dict) and isinstance(data.get("videos"), list) else [data]
        for record in records:
            title = str((record or {}).get("video_title") or (record or {}).get("title") or "")
            lowered = title.lower()
            for term in forbidden_title_terms:
                if term.lower() in lowered:
                    hits.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {term}: {title}")
    assert hits == []


def test_generated_reports_use_repo_relative_posix_paths():
    _ensure_reader_review_report()
    _ensure_review_package_summary()

    report_paths = [
        REPO_ROOT / "outputs" / "reader_review_report.md",
        REPO_ROOT / "outputs" / "review_package" / "review_package_summary.md",
    ]
    path_line_prefixes = ("- Findings source:", "- `", "[File:")
    bad_lines: list[str] = []
    for report_path in report_paths:
        assert report_path.exists(), report_path
        for line in report_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if any(prefix in line for prefix in path_line_prefixes):
                if "D:" in line or "C:" in line or "\\" in line:
                    bad_lines.append(f"{report_path.relative_to(REPO_ROOT).as_posix()}: {line}")
    assert bad_lines == []


def test_report_reader_review_cli_stdout_uses_posix_relative_paths():
    _ensure_rule_findings()
    result = _run_cli(["report-reader-review", "outputs/rule_findings.jsonl"])
    assert "outputs/reader_review_report.md" in result.stdout
    assert "D:" not in result.stdout
    assert "\\" not in result.stdout


def test_active_detector_rules_have_valid_runtime_targets_or_manual_status():
    registry = load_rule_registry(REPO_ROOT / "knowledge_base" / "detector_rules")
    allowed_no_impl = {"disabled", "manual_only", "candidate", "draft_spec_only"}
    allowed_risk_ceilings = {"low", "medium", "high", "risk_signal_only"}
    for rule in registry.values():
        assert rule.risk_ceiling in allowed_risk_ceilings
        assert rule.runtime_status
        has_target = bool(rule.detector_module and rule.detector_function)
        if has_target:
            module = importlib.import_module(rule.detector_module)
            assert callable(getattr(module, rule.detector_function))
        else:
            assert rule.runtime_status in allowed_no_impl


def test_perceptual_hash_does_not_emit_pillow_getdata_deprecation_warning():
    img_a = REPO_ROOT / "examples" / "toy_image_package" / "images" / "img_a.png"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compute_dhash(img_a)
        compute_phash_fallback(img_a)
    messages = [str(w.message) for w in caught]
    assert not any("getdata is deprecated" in message for message in messages)
