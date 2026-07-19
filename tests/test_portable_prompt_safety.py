from __future__ import annotations

from pathlib import Path

from integrity_agent.core.safety import scan_for_forbidden_phrases


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = (
    "review-a-paper-conservatively.md",
    "reconcile-cross-document-claims.md",
    "review-perovskite-source-data.md",
)
REQUIRED_TERMS = (
    "offline by default",
    "human_confirmed",
    "evidence_tier",
    "source_version",
    "counter_evidence",
    "safe_report_language",
    "do_not_overclaim",
)


def test_copy_paste_prompts_keep_the_publication_safety_contract() -> None:
    for filename in PROMPTS:
        path = REPO_ROOT / "prompts" / filename
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for term in REQUIRED_TERMS:
            assert term in lowered, f"{filename} is missing {term}"
        assert "never turn pdf/ocr/model extraction directly into a finding" in lowered
        assert "c:\\users\\" not in lowered


def test_copy_paste_prompts_pass_public_language_scan() -> None:
    assert scan_for_forbidden_phrases(REPO_ROOT / "prompts") == []
