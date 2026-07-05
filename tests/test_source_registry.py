from pathlib import Path

import yaml


ALLOWED_STRENGTHS = {
    "official_institutional",
    "journal_notice",
    "crossref_retraction_watch",
    "publisher_policy",
    "peer_review_platform",
    "news_report",
    "video_public_claim",
    "toy_or_synthetic",
}


def test_source_strength_schema_contains_required_enum_values():
    project_root = Path(__file__).resolve().parents[1]
    registry_path = (
        project_root
        / "knowledge_base"
        / "source_registry"
        / "source_strength_schema.yml"
    )

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    strengths = {item["id"] for item in registry["source_strengths"]}

    assert strengths == ALLOWED_STRENGTHS


def test_case_card_source_types_map_to_source_strength():
    project_root = Path(__file__).resolve().parents[1]
    registry_path = (
        project_root
        / "knowledge_base"
        / "source_registry"
        / "source_strength_schema.yml"
    )
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    source_type_map = registry["source_type_map"]

    case_paths = sorted((project_root / "knowledge_base" / "cases").rglob("*.yml"))
    checked = 0
    for case_path in case_paths:
        card = yaml.safe_load(case_path.read_text(encoding="utf-8"))
        if not isinstance(card, dict) or not card.get("case_id"):
            continue
        source_type = card.get("source_type")
        assert source_type in source_type_map, f"{case_path.name}: {source_type}"
        assert source_type_map[source_type] in ALLOWED_STRENGTHS
        checked += 1

    assert checked >= 12
