from __future__ import annotations

from integrity_agent.core.reporting.html_dashboard import render_dashboard_html
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi


def _record(
    finding_id: str,
    *,
    scope: str = "research_integrity",
    risk: str = "high",
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "scope": scope,
        "finding_category": "general",
        "type": "synthetic_task13_fixture",
        "rule_id": f"rule_{finding_id.lower()}",
        "title": "Synthetic Task 13 fixture",
        "summary": "A synthetic candidate signal requiring review.",
        "safe_report_language": "A synthetic candidate signal requiring review.",
        "risk": risk,
        "risk_level": risk,
        "evidence": [{"source": "tables/toy.csv", "location": "row 1"}],
        "manual_verification": {
            "needed": True,
            "requests": ["Check the supplied fixture."],
        },
        "alternative_explanations": ["Synthetic fixture only."],
        "limitations": ["Synthetic fixture only."],
        "provenance": {"confidence": 1.0},
    }


def test_engineering_and_public_method_context_contribute_zero_to_mrpi() -> None:
    integrity = _record("INTEGRITY", risk="low")
    engineering = _record(
        "ENGINEERING",
        scope="engineering_plausibility",
        risk="high",
    )
    public_method = _record("METHOD-CARD", risk="high")
    public_method.update(
        {
            "finding_category": "public_method_card",
            "type": "public_method_card",
            "source_type": "public_method",
            "public_status": "public_method_example",
        }
    )

    assert calculate_mrpi([engineering]) == 0.0
    assert calculate_mrpi([public_method]) == 0.0
    assert calculate_mrpi([integrity, engineering, public_method]) == 5.0

    dashboard = render_dashboard_html([integrity, engineering, public_method])
    assert '<div class="stat-value">5%</div>' in dashboard
    assert "Engineering Plausibility Questions (Outside Integrity MRPI)" in dashboard
