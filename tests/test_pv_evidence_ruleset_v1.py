from __future__ import annotations

import json

from integrity_agent.domains.photovoltaics.evidence_ruleset_v1 import TAXONOMY_RULESET
from integrity_agent.workflows.pv_ruleset_export import run_pv_ruleset_export
from integrity_agent.core.safety import FORBIDDEN_VERDICT_PHRASES

def test_pv_evidence_ruleset_v1_taxonomy_requirements():
    assert len(TAXONOMY_RULESET) >= 26

    # Verify categories coverage
    expected_categories = {
        "J-V reporting",
        "EQE/J-V",
        "Stability",
        "Tandem",
        "Materials characterization",
    }
    actual_categories = {item.category for item in TAXONOMY_RULESET}
    assert expected_categories.issubset(actual_categories)

    # Validate each taxonomy item
    for item in TAXONOMY_RULESET:
        # Check basic non-emptiness
        assert item.rule_id
        assert item.category
        assert item.required_evidence
        assert item.missing_evidence_signal

        # Every item must have manual verification and benign alternatives
        assert isinstance(item.manual_verification_questions, list)
        assert len(item.manual_verification_questions) >= 1
        assert isinstance(item.benign_alternatives, list)
        assert len(item.benign_alternatives) >= 1
        assert isinstance(item.false_positive_risks, list)
        assert len(item.false_positive_risks) >= 1

        # risk_ceiling must be only low/medium/high
        assert item.risk_ceiling in {"low", "medium", "high"}

        # High risk ceiling must have a raw/source-data verification caveat
        if item.risk_ceiling == "high":
            has_caveat = (
                "raw/source-data" in item.safe_report_language.lower() or
                "raw/source-data" in item.missing_evidence_signal.lower() or
                any("raw" in q.lower() or "source" in q.lower() for q in item.manual_verification_questions)
            )
            assert has_caveat, f"High risk rule {item.rule_id} must have a raw/source-data verification caveat."

        # safe language must not contain forbidden verdict phrases
        safe_lang_lower = item.safe_report_language.lower()
        for forbidden in FORBIDDEN_VERDICT_PHRASES:
            assert forbidden.lower() not in safe_lang_lower, f"Rule {item.rule_id} contains forbidden phrase: {forbidden}"


def test_pv_ruleset_export_helper(tmp_path):
    # Run the export helper into a temporary directory
    json_path, md_path = run_pv_ruleset_export(tmp_path)

    # Check that files were created
    assert json_path.exists()
    assert md_path.exists()

    # Load and validate JSON file structure
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == len(TAXONOMY_RULESET)

    # Check one item in JSON
    first_item = data[0]
    assert "rule_id" in first_item
    assert "category" in first_item
    assert "risk_ceiling" in first_item

    # Check Markdown content
    md_content = md_path.read_text(encoding="utf-8")
    assert "# Photovoltaics (PV) Evidence Ruleset v1 Taxonomy" in md_content
    for item in TAXONOMY_RULESET:
        assert item.rule_id in md_content

    # Check safety disclaimer keywords in exported Markdown
    md_content_lower = md_content.lower()
    assert "not an automatic misconduct detector" in md_content_lower
    assert "manual verification" in md_content_lower
    assert ("source/raw data" in md_content_lower or "raw/source-data" in md_content_lower)
