from __future__ import annotations

from pathlib import Path

import yaml

from integrity_agent.core.safety import scan_for_forbidden_phrases


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = (
    "triage-research-evidence",
    "check-research-consistency",
    "write-safe-integrity-report",
)
REQUIRED_CONTRACT_TERMS = (
    "human_confirmed",
    "evidence_tier",
    "scope",
    "counter_evidence",
    "resolution_status",
    "safe_report_language",
    "do_not_overclaim",
)


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


def test_portable_skills_are_self_contained_and_discoverable() -> None:
    for name in SKILL_NAMES:
        skill_dir = REPO_ROOT / "skills" / name
        skill_path = skill_dir / "SKILL.md"
        metadata_path = skill_dir / "agents" / "openai.yaml"

        assert skill_path.is_file()
        assert metadata_path.is_file()

        frontmatter = _frontmatter(skill_path)
        assert set(frontmatter) == {"name", "description"}
        assert frontmatter["name"] == name
        assert len(str(frontmatter["description"])) >= 80

        body = skill_path.read_text(encoding="utf-8").lower()
        for term in REQUIRED_CONTRACT_TERMS:
            assert term in body, f"{name} is missing {term}"

        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        interface = metadata["interface"]
        assert 25 <= len(interface["short_description"]) <= 64
        assert f"${name}" in interface["default_prompt"]


def test_portable_skills_pass_public_language_scan() -> None:
    assert scan_for_forbidden_phrases(REPO_ROOT / "skills") == []


def test_forward_tested_skills_define_confirmation_counts_and_version_evidence() -> None:
    triage = (
        REPO_ROOT / "skills" / "triage-research-evidence" / "SKILL.md"
    ).read_text(encoding="utf-8").lower()
    consistency = (
        REPO_ROOT / "skills" / "check-research-consistency" / "SKILL.md"
    ).read_text(encoding="utf-8").lower()
    reporting = (
        REPO_ROOT / "skills" / "write-safe-integrity-report" / "SKILL.md"
    ).read_text(encoding="utf-8").lower()
    guide = (REPO_ROOT / "docs" / "USING_WITHOUT_INSTALLATION.md").read_text(
        encoding="utf-8"
    ).lower()

    assert "input `human_confirmed: true`" in triage
    assert "current request" in triage
    assert "counting convention" in triage
    assert "input `human_confirmed: true`" in consistency
    assert "current request" in consistency
    assert "manifest event alone" in consistency
    assert "manifest event alone" in reporting
    assert "not a bundled runner" in guide
    assert "read the supplied file formats" in guide
