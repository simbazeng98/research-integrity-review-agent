from __future__ import annotations

import json
from pathlib import Path
from integrity_agent.core.path_display import display_path
from integrity_agent.domains.photovoltaics.evidence_ruleset_v1 import TAXONOMY_RULESET

def run_pv_ruleset_export(output_dir: Path | str | None = None) -> tuple[Path, Path]:
    if output_dir is None:
        out_path = Path("outputs") / "pv_ruleset_v1"
    else:
        out_path = Path(output_dir)

    out_path.mkdir(parents=True, exist_ok=True)

    json_path = out_path / "pv_evidence_ruleset_v1.json"
    md_path = out_path / "pv_evidence_ruleset_v1.md"

    # Export to JSON
    json_data = [item.to_dict() for item in TAXONOMY_RULESET]
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    # Export to Markdown
    md_lines = [
        "# Photovoltaics (PV) Evidence Ruleset v1 Taxonomy",
        "",
        "> [!IMPORTANT]",
        "> **Safety Notice & Disclaimer**",
        "> - The PV evidence ruleset is a taxonomy of evidence completeness and consistency signals, **not an automatic misconduct detector**.",
        "> - Surfaced signals do **not** confirm, verify, or prove research misconduct, data fabrication, or fraud.",
        "> - Surfaced signals require **manual verification** and thorough **source/raw data** review to determine validity.",
        "",
        "This document lists the 26 taxonomy rules across 5 groups for photovoltaics and materials characterization.",
        "These rules identify evidence completeness and consistency review signals for human review.",
        "",
        "## Summary of Rules by Group",
        ""
    ]

    # Group rules by category
    by_category: dict[str, list] = {}
    for item in TAXONOMY_RULESET:
        by_category.setdefault(item.category, []).append(item)

    for cat, items in by_category.items():
        md_lines.append(f"### {cat} ({len(items)} rules)")
        for item in items:
            md_lines.append(f"- **{item.rule_id}**: {item.missing_evidence_signal} (Risk Ceiling: `{item.risk_ceiling}`)")
        md_lines.append("")

    md_lines.append("## Rule Definitions")
    md_lines.append("")

    for item in TAXONOMY_RULESET:
        md_lines.extend([
            f"### `{item.rule_id}`",
            "",
            f"- **Category**: {item.category}",
            f"- **Risk Ceiling**: `{item.risk_ceiling}`",
            f"- **Required Evidence fields**: " + ", ".join(f"`{e}`" for e in item.required_evidence),
            f"- **Missing Evidence Signal**: {item.missing_evidence_signal}",
            "",
            "#### Safe Report Language",
            f"> {item.safe_report_language}",
            "",
            "#### Manual Verification Questions",
        ])
        for q in item.manual_verification_questions:
            md_lines.append(f"- {q}")

        md_lines.extend([
            "",
            "#### Alternative Benign Explanations",
        ])
        for alt in item.benign_alternatives:
            md_lines.append(f"- {alt}")

        md_lines.extend([
            "",
            "#### False Positive Risks",
        ])
        for risk in item.false_positive_risks:
            md_lines.append(f"- {risk}")

        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines).strip() + "\n")

    print(f"Wrote PV ruleset JSON to: {display_path(json_path)}")
    print(f"Wrote PV ruleset MD to: {display_path(md_path)}")

    return json_path, md_path
