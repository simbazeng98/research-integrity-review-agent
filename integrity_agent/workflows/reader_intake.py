from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from integrity_agent.core.metadata.doi import normalize_doi
from integrity_agent.core.metadata.crossref_client import fetch_crossref_work, CrossrefClientError
from integrity_agent.core.metadata.crossref_updates import parse_crossref_updates

DEFAULT_OUTPUT_DIR = Path("outputs") / "paper_case"


def run_reader_intake(
    doi_input: str,
    allow_network: bool = False,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path]:
    """Execute the reader intake workflow for a given DOI.

    Performs normalization, metadata retrieval (using offline mock or online API),
    and generates outputs/paper_case/metadata.json and outputs/paper_case/intake_summary.md.
    """
    if output_dir is None:
        resolved_dir = DEFAULT_OUTPUT_DIR
    else:
        resolved_dir = Path(output_dir)

    resolved_dir.mkdir(parents=True, exist_ok=True)

    # 1. Normalize DOI
    try:
        normalized_doi = normalize_doi(doi_input)
    except ValueError:
        # Fallback to stripped value if invalid
        normalized_doi = str(doi_input).strip().lower()

    # 2. Fetch metadata
    raw_payload: dict[str, Any] = {}
    title = "Unknown Title"
    publisher = "Unknown Publisher"
    updates_list: list[dict[str, Any]] = []
    
    try:
        raw_payload = fetch_crossref_work(normalized_doi, allow_network=allow_network)
        parsed = parse_crossref_updates(raw_payload)
        status = parsed.status
        
        # Extract title and publisher from message
        message = raw_payload.get("message", {})
        titles = message.get("title", [])
        if titles:
            title = str(titles[0])
        publisher = str(message.get("publisher", "Unknown Publisher"))
        
        for item in parsed.updates:
            updates_list.append({
                "doi": item.doi,
                "update_type": item.update_type,
                "source": item.source,
                "label": item.label,
                "updated_date": item.updated_date,
                "related_doi": item.related_doi,
            })
            
    except CrossrefClientError:
        status = "metadata_unavailable"
        raw_payload = {}

    source_strength = "toy_or_synthetic" if normalized_doi.startswith("10.0000/") else "crossref_metadata"

    # 3. Create metadata.json
    metadata_json = {
        "doi": doi_input,
        "normalized_doi": normalized_doi,
        "status": status,
        "allow_network": allow_network,
        "source_strength": source_strength,
        "title": title,
        "publisher": publisher,
        "updates": updates_list,
        "raw": raw_payload,
    }

    metadata_path = resolved_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 4. Create intake_summary.md
    summary_lines = [
        "# Paper Case Intake Summary",
        "",
        "## Metadata Status",
        f"- Target DOI: `{normalized_doi}`",
        f"- Status: `{status}`",
        f"- Network lookup: {'Performed' if allow_network else 'Not performed'}",
    ]

    if not allow_network and not normalized_doi.startswith("10.0000/"):
        summary_lines.append("- Note: Metadata network lookup was not performed.")

    summary_lines.extend([
        "",
        "## Document Details",
        f"- Title: {title}",
        f"- Publisher: {publisher}",
        f"- Source strength: `{source_strength}`",
        "",
        "## Known Updates",
    ])

    if updates_list:
        for idx, u in enumerate(updates_list, 1):
            summary_lines.append(
                f"{idx}. **{u['update_type'].upper()}** notice ({u['related_doi']}) "
                f"published on {u['updated_date'] or 'unknown date'} (source: {u['source']})."
            )
    else:
        summary_lines.append("- No known updates or retraction notices found in available metadata.")

    summary_lines.extend([
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate risk signals for human review. It does not determine misconduct, intent, or responsibility.",
        "",
    ])

    summary_path = resolved_dir / "intake_summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    return metadata_path.resolve(), summary_path.resolve()
