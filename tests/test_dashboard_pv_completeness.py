from __future__ import annotations


from integrity_agent.core.reporting.html_dashboard import render_dashboard_html

def test_dashboard_pv_completeness_rendering():
    # 1. Test rendering with PV evidence completeness findings
    findings = [
        {
            "finding_id": "PV-RULESET-FIND-001",
            "finding_category": "pv_evidence_completeness",
            "rule_id": "pv_jv_mask_area_completeness",
            "risk_level": "low",
            "evidence": [{"source": "toy_pv.csv", "location": "Table 1"}],
            "manual_verification": {"needed": True, "requests": ["Is the mask area reported?"]},
            "safe_report_language": "Candidate mask area completeness gap.",
            "provenance": {"missing_fields": ["mask_area"]}
        },
        {
            "finding_id": "FIND-002",
            "finding_category": "general_risk",
            "rule_id": "other_rule",
            "risk_level": "medium",
            "evidence": [{"source": "some_file.csv", "location": "Table 2"}],
            "manual_verification": {"needed": True, "requests": ["Review other fields?"]},
            "safe_report_language": "General risk detected."
        }
    ]

    html_out = render_dashboard_html(findings, locale="en")

    # Assert PV completeness section is present
    assert "PV Evidence Completeness Reviews" in html_out
    assert "pv-completeness-card" in html_out
    assert "Missing Fields:" in html_out
    assert "not an automatic misconduct detector" in html_out

    # Assert general findings section does NOT duplicate the completeness finding
    # Let's count how many times PV-RULESET-FIND-001 appears in HTML cards.
    # It should only appear once inside the pv-completeness-card section, not in normal findings
    assert html_out.count("PV-RULESET-FIND-001") == 1
    assert html_out.count("FIND-002") == 1


def test_dashboard_no_pv_completeness_rendering():
    # 2. Test rendering without PV evidence completeness findings
    findings = [
        {
            "finding_id": "FIND-002",
            "finding_category": "general_risk",
            "rule_id": "other_rule",
            "risk_level": "medium",
            "evidence": [{"source": "some_file.csv", "location": "Table 2"}],
            "manual_verification": {"needed": True, "requests": ["Review other fields?"]},
            "safe_report_language": "General risk detected."
        }
    ]

    html_out = render_dashboard_html(findings, locale="en")

    # Assert PV completeness section is NOT present
    assert "PV Evidence Completeness Reviews" not in html_out
    assert "pv-completeness-card" not in html_out
    assert html_out.count("FIND-002") == 1
