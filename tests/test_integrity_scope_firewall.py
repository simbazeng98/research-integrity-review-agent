from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from integrity_agent.core.evidence.ledger_schema import EvidenceRecord
from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)
from integrity_agent.core.evidence.scope import FindingScope, scope_of
from integrity_agent.core.reporting.html_dashboard import render_dashboard_html
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi
from integrity_agent.workflows.report_reader_review import write_reader_review_report


def _record(
    finding_id: str,
    *,
    scope: str | None,
    risk: str = "low",
    summary: str = "Synthetic review item.",
) -> dict[str, object]:
    record: dict[str, object] = {
        "finding_id": finding_id,
        "finding_category": "general",
        "rule_id": f"rule_{finding_id.lower()}",
        "type": "synthetic_scope_fixture",
        "title": "Synthetic scope fixture",
        "summary": summary,
        "safe_report_language": summary,
        "risk": risk,
        "risk_level": risk,
        "evidence": [
            {
                "source": "tables/synthetic.csv",
                "location": "row 1",
            }
        ],
        "manual_verification": {
            "needed": True,
            "requests": ["Check the supplied source record."],
        },
        "alternative_explanations": ["The supplied context may be incomplete."],
        "limitations": ["Synthetic fixture only."],
        "provenance": {"confidence": 1.0},
    }
    if scope is not None:
        record["scope"] = scope
    return record


def test_ledger_scope_is_explicit_and_legacy_records_remain_compatible() -> None:
    legacy = EvidenceRecord.model_validate(_record("LEGACY", scope=None))
    assert legacy.scope is FindingScope.RESEARCH_INTEGRITY

    engineering = EvidenceRecord.model_validate(
        _record(
            "ENGINEERING",
            scope="engineering_plausibility",
            summary="High price and difficult deposition need engineering review.",
        )
    )
    assert engineering.scope is FindingScope.ENGINEERING_PLAUSIBILITY

    # Classification is based on the explicit enum, never summary keywords.
    assert scope_of(
        _record(
            "NO_KEYWORD_GUESS",
            scope="research_integrity",
            summary="High price appears in this explicitly scoped integrity fixture.",
        )
    ) is FindingScope.RESEARCH_INTEGRITY


def test_unsupported_motive_cannot_validate_as_an_evidence_finding() -> None:
    with pytest.raises(ValidationError, match="unsupported_motive"):
        EvidenceRecord.model_validate(
            _record(
                "MOTIVE",
                scope="unsupported_motive",
                summary="Synthetic unsupported-motive assertion fixture.",
            )
        )


def test_engineering_scope_contributes_zero_to_integrity_mrpi() -> None:
    integrity = _record("INTEGRITY", scope="research_integrity", risk="low")
    engineering = _record(
        "ENGINEERING",
        scope="engineering_plausibility",
        risk="high",
        summary="High price and difficult deposition need engineering review.",
    )

    assert calculate_mrpi([integrity]) == 5.0
    assert calculate_mrpi([integrity, engineering]) == 5.0


def test_typed_finding_preserves_explicit_scope_in_ledger_and_mrpi() -> None:
    finding = Finding(
        finding_id="TYPED_ENGINEERING",
        type="synthetic_engineering_question",
        title="Synthetic engineering question",
        risk=RiskLevel.HIGH,
        summary="A deposition constraint needs engineering review.",
        evidence=[EvidenceItem(source="tables/synthetic.csv", location="row 1")],
        manual_verification=ManualVerification(
            needed=True,
            requests=["Check the stated engineering constraint."],
        ),
        scope=FindingScope.ENGINEERING_PLAUSIBILITY,
    )

    assert finding.to_ledger_record()["scope"] == "engineering_plausibility"
    assert calculate_mrpi([finding]) == 0.0
    assert "Engineering Plausibility Questions (Outside Integrity MRPI)" in (
        render_dashboard_html([finding])
    )


def test_reader_report_separates_engineering_and_blocks_unsupported_motive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    integrity = _record(
        "INTEGRITY",
        scope="research_integrity",
        summary="A supplied arithmetic value needs manual verification.",
    )
    engineering = _record(
        "ENGINEERING",
        scope="engineering_plausibility",
        risk="high",
        summary="High price and difficult deposition need engineering review.",
    )
    unsupported = _record(
        "MOTIVE",
        scope="unsupported_motive",
        risk="high",
        summary="Synthetic unsupported-motive assertion fixture.",
    )
    findings_path = tmp_path / "findings.jsonl"
    findings_path.write_text(
        "".join(json.dumps(item) + "\n" for item in [integrity, engineering, unsupported]),
        encoding="utf-8",
    )

    report_path = write_reader_review_report(findings_path, tmp_path / "report.md")
    report = report_path.read_text(encoding="utf-8")

    risk_section = report.split("## Detected risk signals", 1)[1].split(
        "## Engineering plausibility questions", 1
    )[0]
    assert "A supplied arithmetic value needs manual verification." in risk_section
    assert "High price and difficult deposition" not in risk_section
    assert "## Engineering plausibility questions (outside integrity MRPI)" in report
    assert "High price and difficult deposition need engineering review." in report
    assert "Synthetic unsupported-motive assertion fixture." not in report
    assert "Engineering question count: 1" in report


def test_dashboard_separates_engineering_blocks_motive_and_keeps_mrpi_integrity_only() -> None:
    integrity = _record(
        "INTEGRITY",
        scope="research_integrity",
        summary="A supplied arithmetic value needs manual verification.",
    )
    engineering = _record(
        "ENGINEERING",
        scope="engineering_plausibility",
        risk="high",
        summary="High price and difficult deposition need engineering review.",
    )
    unsupported = _record(
        "MOTIVE",
        scope="unsupported_motive",
        risk="high",
        summary="Synthetic unsupported-motive assertion fixture.",
    )

    dashboard = render_dashboard_html([integrity, engineering, unsupported])

    assert '<div class="stat-value">5%</div>' in dashboard
    assert "Engineering Plausibility Questions (Outside Integrity MRPI)" in dashboard
    assert "High price and difficult deposition need engineering review." in dashboard
    assert "Synthetic unsupported-motive assertion fixture." not in dashboard
    assert "Total Findings</span>" in dashboard
    assert '<div class="stat-value">1</div>' in dashboard
