from __future__ import annotations

from integrity_agent.core.reporting.html_dashboard import render_dashboard_html
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi


def _finding(
    finding_id: str,
    *,
    correlation_group: str | None = None,
    source: str = "tables/results.csv",
    table: str = "table-1",
    method_family: str = "numeric_pattern",
) -> dict[str, object]:
    provenance: dict[str, object] = {
        "confidence": 1.0,
        "source": source,
        "table": table,
        "method_family": method_family,
    }
    if correlation_group is not None:
        provenance["correlation_group"] = correlation_group
    return {
        "finding_id": finding_id,
        "scope": "research_integrity",
        "finding_category": "numeric_pattern",
        "type": "synthetic_correlated_signal",
        "rule_id": f"rule_{finding_id.lower()}",
        "title": "Synthetic correlated signal",
        "summary": "A candidate numeric pattern requires manual review.",
        "safe_report_language": "A candidate numeric pattern requires manual review.",
        "risk": "medium",
        "risk_level": "medium",
        "source_file": source,
        "table_id": table,
        "method_family": method_family,
        "evidence": [{"source": source, "location": table}],
        "manual_verification": {
            "needed": True,
            "requests": ["Check the supplied table."],
        },
        "alternative_explanations": ["The columns may share a derivation."],
        "limitations": ["Synthetic fixture only."],
        "provenance": provenance,
    }


def test_explicit_correlation_group_scores_once_but_keeps_all_records() -> None:
    findings = [
        _finding("CORRELATED-A", correlation_group="shared-numeric-group"),
        _finding("CORRELATED-B", correlation_group="shared-numeric-group"),
    ]

    assert calculate_mrpi(findings) == 15.0
    assert [item["finding_id"] for item in findings] == [
        "CORRELATED-A",
        "CORRELATED-B",
    ]

    dashboard = render_dashboard_html(findings)
    assert '<div class="stat-value">15%</div>' in dashboard
    assert dashboard.count("CORRELATED-A") == 1
    assert dashboard.count("CORRELATED-B") == 1


def test_source_table_method_family_fallback_scores_once() -> None:
    findings = [_finding("FALLBACK-A"), _finding("FALLBACK-B")]

    assert calculate_mrpi(findings) == 15.0


def test_different_correlation_groups_remain_independent() -> None:
    findings = [
        _finding("GROUP-A", correlation_group="numeric-group-a"),
        _finding("GROUP-B", correlation_group="numeric-group-b"),
    ]

    assert calculate_mrpi(findings) == 30.0


def test_explicit_group_is_authoritative_across_evidence_sources() -> None:
    findings = [
        _finding(
            "PAIR-A",
            correlation_group="canonical-curve-pair",
            source="tables/curve-a.csv",
        ),
        _finding(
            "PAIR-B",
            correlation_group="canonical-curve-pair",
            source="tables/curve-b.csv",
        ),
    ]

    assert calculate_mrpi(findings) == 15.0
