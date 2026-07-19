from __future__ import annotations

from pathlib import Path

from integrity_agent.core.reporting.html_dashboard import render_dashboard_html


def _finding(risk: str) -> dict[str, object]:
    return {
        "finding_id": f"F-{risk}",
        "rule_id": "toy_consistency_rule",
        "risk_level": risk,
        "title": {"en": "Toy candidate", "zh": "玩具候选信号"},
        "safe_report_language": {
            "en": "Candidate signal requiring manual review.",
            "zh": "需要人工复核的候选信号。",
        },
        "evidence": [{"source": "tables/toy.csv", "location": "row 2"}],
        "manual_verification": ["Check the supplied source table."],
        "alternative_explanations": ["Rounding or export precision."],
    }


def test_dashboard_uses_filterable_accessible_evidence_dossier_ui() -> None:
    rendered = render_dashboard_html(
        [_finding("high"), _finding("medium"), _finding("low")],
        locale="zh",
    )

    assert '<html lang="zh" data-default-locale="zh">' in rendered
    assert 'id="finding-search"' in rendered
    assert 'data-filter-risk="all"' in rendered
    assert 'data-filter-risk="medium"' in rendered
    assert 'aria-live="polite"' in rendered
    assert 'role="progressbar"' in rendered
    assert 'aria-valuenow="' in rendered
    assert 'aria-pressed="true"' in rendered
    assert 'data-finding-card data-risk="high"' in rendered
    assert 'data-finding-card data-risk="medium"' in rendered
    assert 'data-finding-card data-risk="low"' in rendered
    assert 'class="skip-link"' in rendered

    assert "#101513" in rendered
    assert "#f3f0e8" in rendered.lower()
    assert "#b48838" in rendered.lower()
    assert "#b43d32" in rendered.lower()
    assert "#1c4b3d" in rendered.lower()

    forbidden_fonts = ("Arial", "Helvetica", "system-ui", "-apple-system")
    assert not any(font in rendered for font in forbidden_fonts)
    assert "\u26a0" not in rendered


def test_all_html_reporters_avoid_runtime_font_requests() -> None:
    root = Path(__file__).resolve().parents[1]
    reporters = (
        root / "integrity_agent/workflows/report_pv_domain_html.py",
        root / "integrity_agent/workflows/report_raw_pv_html.py",
    )
    for reporter in reporters:
        source = reporter.read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in source
        assert "fonts.gstatic.com" not in source
