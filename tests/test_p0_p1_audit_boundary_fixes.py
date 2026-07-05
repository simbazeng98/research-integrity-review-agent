import json
import subprocess
import sys
from pathlib import Path

import yaml

from integrity_agent.__main__ import build_parser
from integrity_agent.workflows.geng_video_distillation import build_geng_video_index, fixture_metadata_fetcher
from integrity_agent.workflows.report_reader_review import write_reader_review_report


def test_geng_video_index_cli_defaults_to_fixture_without_network(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    seed = tmp_path / "private_video_corpora" / "geng_bilibili" / "seed_urls.txt"
    seed.parent.mkdir(parents=True)
    seed.write_text("https://www.bilibili.com/video/BV1synthetic01/\n", encoding="utf-8")
    index = tmp_path / "outputs" / "geng_video_distillation" / "geng_video_index.yml"
    private_root = tmp_path / "private_video_corpora" / "geng_bilibili"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "geng-video-index",
            str(seed),
            "--output",
            str(index),
            "--private-root",
            str(private_root),
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (private_root / "raw_metadata" / "BV1synthetic01.json").exists()
    assert not (private_root / "private_transcripts" / "BV1synthetic01.txt").exists()
    index_data = yaml.safe_load(index.read_text(encoding="utf-8"))
    assert index_data["videos"][0]["subtitle_status"] == "fixture_metadata_only"
    assert index_data["videos"][0]["transcript_private_path"] is None
    assert index_data["videos"][0]["private_cache_written"] is False


def test_geng_video_index_live_metadata_requires_allow_network(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    seed = tmp_path / "seed_urls.txt"
    seed.write_text("https://www.bilibili.com/video/BV1synthetic01/\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "geng-video-index",
            str(seed),
            "--metadata-mode",
            "live",
            "--output",
            str(tmp_path / "index.yml"),
            "--private-root",
            str(tmp_path / "private"),
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--allow-network" in result.stderr


def test_geng_video_generated_artifact_defaults_are_under_outputs():
    parser = build_parser()

    index_args = parser.parse_args(["geng-video-index", "private_video_corpora/geng_bilibili/seed_urls.txt"])
    assert index_args.metadata_mode == "fixture"
    assert index_args.output.as_posix() == "outputs/geng_video_distillation/geng_video_index.yml"

    distill_args = parser.parse_args(["geng-video-distill", "outputs/geng_video_distillation/geng_video_index.yml"])
    assert distill_args.output_dir.as_posix() == "outputs/geng_video_distillation/cases"

    rule_args = parser.parse_args(["geng-video-rule-candidates", "outputs/geng_video_distillation/cases"])
    assert rule_args.output_dir.as_posix() == "outputs/geng_video_distillation/rule_candidates"


def test_private_video_corpus_preflight_writes_local_only_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("private_video_corpora/\nprivate_transcripts/\nprivate_chunk_notes/\n", encoding="utf-8")
    seed = tmp_path / "private_video_corpora" / "geng_bilibili" / "seed_urls.txt"
    seed.parent.mkdir(parents=True)
    seed.write_text("https://www.bilibili.com/video/BV1synthetic01/\n", encoding="utf-8")

    build_geng_video_index(
        seed,
        index_path=tmp_path / "outputs" / "geng_video_distillation" / "geng_video_index.yml",
        private_root=tmp_path / "private_video_corpora" / "geng_bilibili",
        fetcher=fixture_metadata_fetcher,
    )

    sentinel = tmp_path / "private_video_corpora" / "geng_bilibili" / "LOCAL_ONLY_DO_NOT_COMMIT.txt"
    assert sentinel.exists()
    assert "local-only private corpus" in sentinel.read_text(encoding="utf-8")


def test_reader_review_report_uses_repo_relative_findings_source(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    findings_path = project_root / "outputs" / "tmp_abs_path_test" / "rule_findings.jsonl"
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings_path.write_text(
        json.dumps(
            {
                "rule_id": "numeric_fixed_delta_between_columns",
                "risk_level": "medium",
                "safe_report_language": "Candidate signal requiring verification.",
                "evidence_items": [],
                "alternative_explanations": [],
                "missing_verification_materials": [],
                "suggested_verification_questions": [],
                "limitations": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "reader_review_report.md"

    write_reader_review_report(findings_path, output_path=report_path)
    report = report_path.read_text(encoding="utf-8")

    assert "- Findings source: `outputs/tmp_abs_path_test/rule_findings.jsonl`" in report
    assert str(project_root).replace("\\", "/") not in report.replace("\\", "/")


def test_geng_video_fixture_index_does_not_clobber_existing_private_asr_transcript(tmp_path):
    seed = tmp_path / "seed_urls.txt"
    seed.write_text("https://www.bilibili.com/video/BV1synthetic01/\n", encoding="utf-8")
    private_root = tmp_path / "private_video_corpora" / "geng_bilibili"
    transcript = private_root / "private_transcripts" / "BV1synthetic01.txt"
    transcript.parent.mkdir(parents=True)
    transcript.write_text("# PRIVATE ASR transcript — do not commit/publicize full text\n[0.00-1.00] real local ASR\n", encoding="utf-8")

    build_geng_video_index(
        seed,
        index_path=tmp_path / "outputs" / "geng_video_distillation" / "geng_video_index.yml",
        private_root=private_root,
        fetcher=fixture_metadata_fetcher,
    )

    assert "real local ASR" in transcript.read_text(encoding="utf-8")


def test_geng_video_fixture_index_does_not_clobber_existing_private_raw_metadata(tmp_path):
    seed = tmp_path / "seed_urls.txt"
    seed.write_text("https://www.bilibili.com/video/BV1synthetic01/\n", encoding="utf-8")
    private_root = tmp_path / "private_video_corpora" / "geng_bilibili"
    raw_metadata = private_root / "raw_metadata" / "BV1synthetic01.json"
    raw_metadata.parent.mkdir(parents=True)
    raw_metadata.write_text(
        json.dumps({"bvid": "BV1synthetic01", "title": "Real local videoInfo", "local_download_dir": "local_private_download_dir"}, ensure_ascii=False),
        encoding="utf-8",
    )

    build_geng_video_index(
        seed,
        index_path=tmp_path / "outputs" / "geng_video_distillation" / "geng_video_index.yml",
        private_root=private_root,
        fetcher=fixture_metadata_fetcher,
    )

    restored = json.loads(raw_metadata.read_text(encoding="utf-8"))
    assert restored["title"] == "Real local videoInfo"
    assert "local_download_dir" in restored


def test_gitignore_ignores_all_test_cache_directories():
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / ".gitignore").read_text(encoding="utf-8")
    assert ".test_cache*/" in text
