from __future__ import annotations

import json
from pathlib import Path

import pytest

from integrity_agent.core.reporting.html_dashboard import render_dashboard_html
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi
from integrity_agent.workflows.report_reader_review import write_reader_review_report


def _resolved_record() -> dict[str, object]:
    return {
        "finding_id": "VERSION-HISTORY-001",
        "scope": "research_integrity",
        "finding_category": "cross_document_claim_consistency",
        "type": "visible_consistency_issue",
        "rule_id": "cross_document_claim_consistency",
        "title": "Historical cross-document value mismatch",
        "summary": "A historical source-version difference was reconciled.",
        "safe_report_language": (
            "A historical source-version difference is retained for traceability."
        ),
        "risk": "medium",
        "risk_level": "medium",
        "evidence_tier": "E3",
        "source_version": "publisher-v1",
        "resolution_status": "resolved_by_version",
        "counter_evidence": [
            {
                "event_id": "publisher-current-unique-marker",
                "source_type": "current_publisher_si",
                "source_version": "publisher-v2",
                "source_url": "https://publisher.example/current-si",
            }
        ],
        "do_not_overclaim": "UNIQUE-DO-NOT-OVERCLAIM-MARKER: status is not intent.",
        "evidence": [
            {
                "source": "documents/claims.jsonl",
                "location": "claim-main vs claim-si",
            }
        ],
        "manual_verification": {
            "needed": True,
            "requests": ["Check the current publisher-hosted version."],
        },
        "alternative_explanations": ["An older supplementary file was cached."],
        "limitations": ["Only supplied, human-confirmed claims were compared."],
        "provenance": {
            "confidence": 1.0,
            "source_version": "publisher-v1",
            "resolution_status": "resolved_by_version",
            "counter_evidence": [
                {
                    "event_id": "publisher-current-unique-marker",
                    "source_type": "current_publisher_si",
                    "source_version": "publisher-v2",
                }
            ],
            "do_not_overclaim": (
                "UNIQUE-DO-NOT-OVERCLAIM-MARKER: status is not intent."
            ),
        },
    }


def test_resolved_by_version_is_not_scored_as_an_open_medium_finding() -> None:
    # Resolution state itself is a scoring contract.  A caller should not have
    # to duplicate open_for_scoring/mrpi_eligible flags to avoid re-scoring a
    # historical mismatch.
    assert calculate_mrpi([_resolved_record()]) == 0.0


def test_version_and_counter_evidence_fields_render_in_report_and_dashboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    record = _resolved_record()
    ledger_path = tmp_path / "findings.jsonl"
    ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    report_path = write_reader_review_report(ledger_path, tmp_path / "report.md")
    report = report_path.read_text(encoding="utf-8")
    dashboard = render_dashboard_html([record])

    for rendered in (report, dashboard):
        assert "Evidence tier" in rendered
        assert "E3" in rendered
        assert "Source version" in rendered
        assert "publisher-v1" in rendered
        assert "Resolution status" in rendered
        assert "resolved_by_version" in rendered
        assert "Counter-evidence" in rendered
        assert "publisher-current-unique-marker" in rendered
        assert "UNIQUE-DO-NOT-OVERCLAIM-MARKER" in rendered

    assert '<div class="stat-value">0%</div>' in dashboard
