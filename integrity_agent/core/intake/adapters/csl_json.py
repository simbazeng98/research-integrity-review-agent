from __future__ import annotations

import json
from pathlib import Path

from integrity_agent.core.intake.batch_schema import LiteratureItem
from integrity_agent.core.metadata.doi import normalize_doi


def parse_csl_json(file_path: Path) -> list[LiteratureItem]:
    """Parse citation metadata from a CSL JSON export file."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid CSL JSON format: {e}")

    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        raise ValueError("CSL JSON must be a list or a single JSON object mapping.")

    items: list[LiteratureItem] = []
    source_file = file_path.name

    for idx, entry in enumerate(data, 1):
        item_id = str(entry.get("id", f"csl-{idx}"))

        # Extract DOI
        doi_val = None
        for key in ["DOI", "doi"]:
            if key in entry:
                doi_val = entry[key]
                break

        if doi_val is not None:
            doi_val = str(doi_val).strip()

        # Extract Title
        title_val = entry.get("title")
        if isinstance(title_val, list) and title_val:
            title_val = str(title_val[0])
        elif title_val is not None:
            title_val = str(title_val)

        # Extract Year
        year_val = None
        issued = entry.get("issued")
        if isinstance(issued, dict):
            date_parts = issued.get("date-parts")
            if date_parts and isinstance(date_parts, list) and date_parts[0]:
                year_val = str(date_parts[0][0])
            elif "raw" in issued:
                year_val = str(issued["raw"])
        elif isinstance(issued, str):
            year_val = issued

        # Extract Journal / Container Title
        journal_val = entry.get("container-title")
        if isinstance(journal_val, list) and journal_val:
            journal_val = str(journal_val[0])
        elif journal_val is not None:
            journal_val = str(journal_val)

        warnings: list[str] = []
        normalized = None

        if doi_val:
            try:
                normalized = normalize_doi(doi_val)
            except ValueError as e:
                warnings.append(f"Invalid DOI format: {doi_val} ({e})")
        else:
            warnings.append("Missing DOI for item.")

        items.append(
            LiteratureItem(
                item_id=item_id,
                source_file=source_file,
                source_format="csl_json",
                doi=doi_val,
                normalized_doi=normalized,
                title=title_val,
                year=year_val,
                journal=journal_val,
                warnings=warnings,
            )
        )

    return items
