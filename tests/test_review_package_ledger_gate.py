from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from integrity_agent.__main__ import main as cli_main
from integrity_agent.core.reporting.html_dashboard import render_dashboard_html
from integrity_agent.workflows.review_package import run_review_package
from integrity_agent.workflows.report_reader_review import write_reader_review_report
from integrity_agent.workflows.validate_ledger import (
    LedgerValidationIssue,
    LedgerValidationResult,
)


def test_final_unified_ledger_validation_failure_blocks_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    output_dir = tmp_path / "output"
    validated_paths: list[Path] = []

    def reject_final_unified_ledger(path: Path | str) -> LedgerValidationResult:
        candidate = Path(path)
        validated_paths.append(candidate)
        if candidate.name == "unified_evidence_index.jsonl":
            return LedgerValidationResult(
                records=1,
                issues=[
                    LedgerValidationIssue(
                        line=1,
                        kind="schema error",
                        message="synthetic final-ledger validation failure",
                    )
                ],
            )
        return LedgerValidationResult(records=0)

    monkeypatch.setattr(
        "integrity_agent.workflows.validate_ledger.validate_ledger_file",
        reject_final_unified_ledger,
    )

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(output_dir),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    assert any(path.name == "unified_evidence_index.jsonl" for path in validated_paths)
    assert summary.overall_status == "failed"
    validation_statuses = [
        status
        for status in summary.module_statuses
        if "ledger" in status.module_name or "unified" in status.module_name
    ]
    assert any(status.status == "failed" for status in validation_statuses)
    assert any(
        "synthetic final-ledger validation failure" in (status.error_message or "")
        for status in validation_statuses
    )


@pytest.mark.parametrize("command", ["review-package", "run-audit"])
def test_failed_review_summary_produces_nonzero_cli_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    failed_status = SimpleNamespace(
        module_name="synthetic-ledger-gate",
        status="failed",
        error_message="synthetic diagnostic marker",
        skip_reason="synthetic_failure",
    )
    monkeypatch.setattr(
        "integrity_agent.workflows.review_package.run_review_package",
        lambda **kwargs: SimpleNamespace(
            overall_status="failed",
            module_statuses=[failed_status],
        ),
    )

    assert cli_main([command, str(tmp_path / "package")]) != 0
    stderr = capsys.readouterr().err
    assert "synthetic-ledger-gate" in stderr
    assert "synthetic diagnostic marker" in stderr


def test_malformed_child_ledger_cannot_be_silently_dropped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = tmp_path / "package"
    documents_dir = package_dir / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "decay_fit_records.jsonl").write_text("{}\n", encoding="utf-8")

    def write_malformed_child(records_path, output_dir):
        del records_path
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        findings = output / "pv_decay_fit_findings.jsonl"
        summary = output / "pv_decay_fit_summary.md"
        findings.write_text("{not-json}\n", encoding="utf-8")
        summary.write_text("synthetic malformed child\n", encoding="utf-8")
        return findings, summary

    monkeypatch.setattr(
        "integrity_agent.workflows.pv_domain_review.run_pv_decay_fit_review",
        write_malformed_child,
    )

    summary = run_review_package(
        package_dir=str(package_dir),
        output_dir=str(tmp_path / "output"),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    assert summary.overall_status == "failed"
    aggregation = next(
        status
        for status in summary.module_statuses
        if status.module_name == "unified-evidence-aggregation"
    )
    assert aggregation.status == "failed"
    assert "invalid JSON" in (aggregation.error_message or "")


def test_reporters_reject_posix_private_paths_defense_in_depth(
    tmp_path: Path,
) -> None:
    record = {
        "finding_id": "PRIVATE-PATH-NEGATIVE-FIXTURE",
        "finding_category": "general",
        "type": "synthetic_negative_fixture",
        "rule_id": "synthetic_negative_fixture",
        "title": "Synthetic negative fixture",
        "summary": "Candidate signal requiring manual review.",
        "safe_report_language": "Candidate signal requiring manual review.",
        "risk": "low",
        "risk_level": "low",
        "evidence": [
            {
                "source": "/" + "home/private-user/paper.pdf",
                "location": "local source",
            }
        ],
        "manual_verification": {
            "needed": True,
            "requests": ["Check the supplied source."],
        },
        "alternative_explanations": [],
        "limitations": [],
    }
    ledger = tmp_path / "unsafe.jsonl"
    import json

    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="private|path"):
        write_reader_review_report(ledger, tmp_path / "report.md")
    with pytest.raises(ValueError, match="private|path"):
        render_dashboard_html([record])
