from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
HERO_PATH = REPO_ROOT / "docs" / "assets" / "evidence-dossier-hero.svg"


def test_readme_has_a_self_contained_evidence_dossier_hero() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/assets/evidence-dossier-hero.svg" in readme
    assert HERO_PATH.exists()

    hero = HERO_PATH.read_text(encoding="utf-8")
    for colour in ("#101419", "#F4F0E6", "#C99A3D", "#A84A3A", "#275C4A"):
        assert colour in hero

    assert "<script" not in hero.lower()
    assert "<image" not in hero.lower()
    assert 'href="http://' not in hero.lower()
    assert 'href="https://' not in hero.lower()
    assert "url(http" not in hero.lower()
    assert "purple" not in hero.lower()

    external_images = re.findall(
        r"(?:!\[[^\]]*\]\(|<img\s+[^>]*src=[\"'])(https?://[^\"')>]+)",
        readme,
        flags=re.IGNORECASE,
    )
    assert external_images == []


def test_readme_explains_the_product_boundary_and_two_use_routes_in_30_seconds() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    lower = readme.lower()

    assert "30-second overview" in lower
    for expected in (
        "evidence ledger",
        "candidate risk signals",
        "manual verification requests",
        "does not determine research misconduct",
    ):
        assert expected in lower

    assert "[Install and run locally](#install-and-run-locally)" in readme
    assert "[Use agent skills](skills/)" in readme
    assert "[Paste ready-to-use prompts](prompts/)" in readme
    assert "[No-install guide](docs/USING_WITHOUT_INSTALLATION.md)" in readme


def test_readme_credits_public_method_inspiration_without_republishing_social_content() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    lower = readme.lower()

    assert "钙钛矿纠察队长" in readme
    assert "耿同学讲故事" in readme
    assert "independent open-source implementation" in lower
    assert "no affiliation or endorsement" in lower
    assert "method and discovery leads only" in lower
    assert "independent verification" in lower
    assert "[Perovskite public method cards](knowledge_base/cases/perovskite_public_methods/)" in readme
    assert "[Geng video method cards](knowledge_base/cases/geng_video_cases/)" in readme

    for forbidden in (
        "18103013029",
        "小红书号",
        "IP属地",
        "xsec_token",
        "space.bilibili.com",
        "xiaohongshu.com/user",
    ):
        assert forbidden not in readme


def test_readme_lists_current_integrity_review_capabilities_without_verdict_language() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    lower = readme.lower()

    for capability in (
        "cross-document claim consistency",
        "version reconciliation",
        "quantization-grid",
        "curve-segment similarity",
        "trpl/tpv",
        "materials process lineage",
        "engineering plausibility",
    ):
        assert capability in lower

    for forbidden in (
        "fraud confirmed",
        "misconduct confirmed",
        "学术不端已证实",
        "造假",
    ):
        assert forbidden not in lower


def test_readme_names_the_actual_review_package_outputs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    for output_name in (
        "unified_evidence_index.jsonl",
        "review_package_summary.md",
        "review_package_dashboard.html",
        "module_status.jsonl",
        "review_package_manifest.json",
    ):
        assert output_name in readme

    assert "reader_review_report.md" not in readme
    assert "review_package_summary.yml" not in readme
