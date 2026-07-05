import json
import subprocess
import sys
from pathlib import Path

import yaml


def test_case_distill_cli_generates_jsonl_ledger(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_note = tmp_path / "toy_case.md"
    output_path = tmp_path / "evidence_ledger.jsonl"
    case_note.write_text(
        "\n".join(
            [
                "# Toy source-data mismatch",
                "",
                "This synthetic note describes a source data mismatch in Table S1.",
                "It is intentionally toy data, not a real paper.",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "case-distill",
            str(case_note),
            "--output",
            str(output_path),
        ],
        check=False,
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    assert records[0]["type"] == "case_distillation_note"
    assert records[0]["risk"] == "low"
    assert records[0]["needs_manual_review"] is True
    assert "source data mismatch" in records[0]["summary"].lower()


def test_case_distill_cli_preserves_relative_source_path(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "evidence_ledger.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "case-distill",
            "examples/toy_case.md",
            "--output",
            str(output_path),
        ],
        check=False,
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert record["evidence"][0]["source"] == "examples/toy_case.md"


def test_case_distill_cli_warns_on_yaml_missing_source_url_and_marks_allegation(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_yaml = tmp_path / "allegation_case.yml"
    output_path = tmp_path / "ledger.jsonl"
    case_yaml.write_text(
        yaml.safe_dump(
            {
                "case_id": "toy_allegation_without_source_url",
                "source_type": "toy_case",
                "public_status": "allegation",
                "safe_report_language": "candidate risk signal requiring review",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "case-distill",
            str(case_yaml),
            "--output",
            str(output_path),
        ],
        check=False,
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "missing source_url" in result.stderr
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert "not independently verified" in record["limitations"]


def test_case_distill_cli_errors_on_invalid_public_status(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_yaml = tmp_path / "invalid_status.yml"
    output_path = tmp_path / "ledger.jsonl"
    case_yaml.write_text(
        yaml.safe_dump(
            {
                "case_id": "toy_invalid_status",
                "source_url": "https://example.test/case",
                "source_type": "toy_case",
                "public_status": "misconduct_proven",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "case-distill",
            str(case_yaml),
            "--output",
            str(output_path),
        ],
        check=False,
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "ERROR" in result.stderr
    assert "public_status" in result.stderr
    assert not output_path.exists()


def test_case_distill_cli_requires_official_source_for_confirmed_misconduct(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_yaml = tmp_path / "confirmed_without_official.yml"
    output_path = tmp_path / "ledger.jsonl"
    case_yaml.write_text(
        yaml.safe_dump(
            {
                "case_id": "toy_confirmed_without_official",
                "source_url": "https://example.test/case",
                "source_type": "news_article",
                "public_status": "confirmed_misconduct",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "case-distill",
            str(case_yaml),
            "--output",
            str(output_path),
        ],
        check=False,
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "official_or_institutional_source" in result.stderr
    assert not output_path.exists()
