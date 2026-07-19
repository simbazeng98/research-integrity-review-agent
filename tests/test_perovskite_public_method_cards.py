from __future__ import annotations

import re
from pathlib import Path

import yaml

from integrity_agent.core.safety import find_runtime_safety_issues
from integrity_agent.core.evidence.scope import FindingScope
from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi
from integrity_agent.workflows.case_distill import distill_yaml_case, validate_case_card


CARD_SPECS = {
    "xhs_ne_quantization_grid_2026.yml": (
        "6a51e989000000001603ea0b",
        "10.1038/s41560-026-02067-w",
    ),
    "xhs_ees_cross_document_2026.yml": (
        "6a4f42f3000000001702c2e9",
        "10.1039/d6ee00301j",
    ),
    "xhs_afm_decay_dls_2026.yml": (
        "6a4a1d3b0000000015027bc0",
        "10.1002/adfm.76562",
    ),
    "xhs_aem_pce_recalculation_2022.yml": (
        "6a48c03b0000000017029e9c",
        "10.1002/aenm.202103674",
    ),
    "xhs_afm_manufacturability_boundary_2026.yml": (
        "6a426fb70000000016026d5c",
        "10.1002/adfm.76623",
    ),
    "xhs_afm_response_version_drift_2026.yml": (
        "6a4b90570000000011011c56",
        "10.1002/adfm.76562",
    ),
}

ALLOWED_CARD_FIELDS = {
    "case_id",
    "priority",
    "field",
    "scope",
    "source_type",
    "source_url",
    "feed_id",
    "source_accessed_at",
    "target_doi",
    "public_status",
    "summary",
    "evidence_tier",
    "evidence_patterns",
    "detector_candidates",
    "manual_verification_needed",
    "false_positive_risks",
    "alternative_explanations",
    "safe_report_language",
    "limitations",
    "counter_sources",
    "resolution_status",
    "version_timeline",
}

CARD_SCOPES = {
    filename: (
        "engineering_plausibility"
        if filename == "xhs_afm_manufacturability_boundary_2026.yml"
        else "research_integrity"
    )
    for filename in CARD_SPECS
}

PROHIBITED_CARD_KEYS = {
    "post_text",
    "raw_post",
    "raw_json",
    "comments",
    "commenter",
    "commenter_identity",
    "article_text",
    "pdf_text",
    "si_text",
    "transcript",
}


def _case_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "knowledge_base"
        / "cases"
        / "perovskite_public_methods"
    )


def _load_cards() -> dict[str, dict]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(_case_dir().glob("*.yml"))
    }


def test_six_perovskite_public_method_cards_validate_and_match_clean_sources():
    cards = _load_cards()

    assert set(cards) == set(CARD_SPECS)
    for filename, (feed_id, target_doi) in CARD_SPECS.items():
        card = cards[filename]
        validation = validate_case_card(card)

        assert not validation.warnings, filename
        assert card["source_type"] == "public_method"
        assert card["source_url"] == (
            f"https://www.xiaohongshu.com/explore/{feed_id}"
        )
        assert card["feed_id"] == feed_id
        assert card["target_doi"] == target_doi
        assert card["source_accessed_at"] == "2026-07-11"
        assert card["public_status"] in {"public_method_example", "unresolved"}
        assert card["scope"] == CARD_SCOPES[filename]
        assert len(card["false_positive_risks"]) >= 2
        assert len(card["manual_verification_needed"]) >= 2
        limitations = " ".join(card["limitations"]).lower()
        assert (
            "social claims and commenter identities are not independently verified"
            in limitations
        )


def test_public_method_cards_keep_only_distilled_metadata_and_safe_language():
    for filename, card in _load_cards().items():
        unexpected = set(card) - ALLOWED_CARD_FIELDS
        assert not unexpected, f"{filename} has unexpected fields: {sorted(unexpected)}"
        assert not (set(card) & PROHIBITED_CARD_KEYS), filename
        assert not find_runtime_safety_issues(card), filename

        serialized = yaml.safe_dump(card, allow_unicode=True).lower()
        for marker in (
            "xsec_" + "token",
            "cookie",
            "qr_code",
            "session_" + "token",
        ):
            assert marker not in serialized, filename
        assert not re.search(
            r"(?:(?<![a-z0-9])[a-z]:[\\/]|\\\\[^\\]+\\)",
            serialized,
        ), filename


def test_afm_decay_card_links_the_public_response_as_counter_evidence():
    cards = _load_cards()
    critique = cards["xhs_afm_decay_dls_2026.yml"]
    response = cards["xhs_afm_response_version_drift_2026.yml"]
    response_url = (
        "https://www.xiaohongshu.com/explore/6a4b90570000000011011c56"
    )

    assert critique["counter_sources"] == [
        {
            "url": response_url,
            "source_type": "author_response",
            "observed_at": "2026-07-11",
        }
    ]
    assert critique["resolution_status"] == "partially_explained"
    assert response["source_url"] == response_url
    assert response["resolution_status"] == "partially_explained"


def test_manufacturability_card_distills_outside_integrity_mrpi():
    card_path = _case_dir() / "xhs_afm_manufacturability_boundary_2026.yml"

    finding, warnings = distill_yaml_case(card_path)

    assert not warnings
    assert finding.scope is FindingScope.ENGINEERING_PLAUSIBILITY
    assert finding.to_ledger_record()["scope"] == "engineering_plausibility"
    assert calculate_mrpi([finding]) == 0.0
