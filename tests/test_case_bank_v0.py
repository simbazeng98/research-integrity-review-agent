from pathlib import Path

import yaml


REQUIRED_FIELDS = {
    "case_id",
    "priority",
    "source_type",
    "source_url",
    "field",
    "public_status",
    "evidence_patterns",
    "detector_candidates",
    "manual_verification_needed",
    "false_positive_risks",
    "safe_report_language",
}

EXPECTED_CASE_FILES = {
    "ori_ke_2026_western_blot_microscopy.yml",
    "ori_andrade_2026_relabeling_grant_data.yml",
    "geng_tongji_numeric_anomaly_2026.yml",
    "hindawi_paper_mill_mass_retractions_2023.yml",
    "nejm_ai_manipulated_clinical_image_2026.yml",
    "ranga_dias_superconductivity_data_reliability.yml",
    "alzheimer_abeta56_image_integrity.yml",
    "dana_farber_image_duplication_cluster.yml",
    "problematic_paper_screener_tortured_phrases.yml",
    "withdrarxiv_withdrawal_taxonomy.yml",
    "western_blot_ai_detector_limitations.yml",
    "western_blot_synthetic_manipulation_localization.yml",
}

EXPECTED_DETECTOR_SPECS = {
    "numeric_terminal_digit_anomaly.yml",
    "numeric_fixed_delta_between_columns.yml",
    "measurement_precision_anomaly.yml",
    "image_lane_duplication_flip.yml",
    "image_cut_paste_noise_pattern.yml",
    "relabeled_source_data.yml",
    "ai_modified_clinical_image.yml",
    "paper_mill_tortured_phrase.yml",
    "retraction_metadata_check.yml",
}

PUBLIC_STATUS_ENUM = {
    "confirmed_misconduct",
    "allegation",
    "investigation_started",
    "retracted",
    "mass_retraction",
    "settlement_or_legal_resolution",
    "published_method",
    "public_method_example",
    "policy_resource",
    "unresolved",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_case_cards():
    case_dir = project_root() / "knowledge_base" / "cases" / "case_bank_v0"
    case_paths = sorted(case_dir.glob("*.yml"))
    return [
        (path, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in case_paths
    ]


def test_case_bank_v0_contains_named_first_batch_of_twelve_cards():
    case_dir = project_root() / "knowledge_base" / "cases" / "case_bank_v0"
    found = {path.name for path in case_dir.glob("*.yml")}

    assert EXPECTED_CASE_FILES <= found


def test_case_bank_v0_cards_have_safe_review_contract():
    for path, card in load_case_cards():
        missing = REQUIRED_FIELDS - set(card)
        assert not missing, f"{path.name} missing fields: {sorted(missing)}"
        assert card["public_status"] in PUBLIC_STATUS_ENUM
        assert card["evidence_patterns"], f"{path.name} needs evidence patterns"
        assert card["detector_candidates"], f"{path.name} needs detector candidates"
        assert card["manual_verification_needed"], f"{path.name} needs manual review"
        assert card["false_positive_risks"], f"{path.name} needs false-positive risks"
        safe_language = card["safe_report_language"].lower()
        assert "risk signal" in safe_language or "candidate" in safe_language
        assert "misconduct proven" not in safe_language
        if card["public_status"] == "confirmed_misconduct":
            assert card.get("official_or_institutional_source"), path.name
        if card["public_status"] == "allegation":
            assert "not independently verified" in card.get("limitations", [])


def test_detector_rule_drafts_exist_for_case_bank_v0():
    detector_dir = project_root() / "knowledge_base" / "detector_rules"
    found = {path.name for path in detector_dir.glob("*.yml")}

    assert EXPECTED_DETECTOR_SPECS <= found


def test_case_schema_documents_status_enum_and_required_fields():
    schema_path = project_root() / "knowledge_base" / "cases" / "case_schema.yml"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))

    assert set(schema["required_fields"]) >= REQUIRED_FIELDS
    assert set(schema["public_status_enum"]) >= PUBLIC_STATUS_ENUM
    assert "bilibili_video_transcripts" in schema["prohibited_public_content"]
