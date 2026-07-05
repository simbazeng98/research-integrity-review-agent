from __future__ import annotations

import re
from pathlib import Path

from integrity_agent.core.intake.batch_schema import LiteratureItem
from integrity_agent.core.metadata.doi import normalize_doi


def parse_bibtex(file_path: Path) -> list[LiteratureItem]:
    """Parse BibTeX entries (.bib) using a robust lightweight regex parser.

    Does not install complex parser libraries. Exposes a clean TODO for RIS format.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")

    # Locate BibTeX entries matching @type{cite_key,
    entry_start_re = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
    matches = list(entry_start_re.finditer(content))

    items: list[LiteratureItem] = []
    source_file = file_path.name

    for idx, match in enumerate(matches):
        item_id = match.group(2)

        # Get the range of the current entry block
        start_pos = match.start()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        entry_text = content[start_pos:end_pos]

        # Regex for standard fields: key = {value} or key = "value" or key = numeric_value
        field_re = re.compile(r"(\w+)\s*=\s*(?:\{([\s\S]*?)\}|\"([\s\S]*?)\"|(\d+))")
        fields: dict[str, str] = {}

        for f_match in field_re.finditer(entry_text):
            f_name = f_match.group(1).lower().strip()
            # Capture the first non-None value from matching groups
            f_val = f_match.group(2) or f_match.group(3) or f_match.group(4)
            if f_val is not None:
                # Clean up braces and collapse whitespace
                f_val = " ".join(f_val.split()).strip()
                fields[f_name] = f_val

        doi_val = fields.get("doi")
        title_val = fields.get("title")
        year_val = fields.get("year")
        journal_val = fields.get("journal") or fields.get("booktitle")

        # Clean title braces if any: e.g. "{Micro-structural Analysis}" -> "Micro-structural Analysis"
        if title_val and title_val.startswith("{") and title_val.endswith("}"):
            title_val = title_val[1:-1].strip()

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
                source_format="bibtex",
                doi=doi_val,
                normalized_doi=normalized,
                title=title_val,
                year=year_val,
                journal=journal_val,
                warnings=warnings,
            )
        )

    return items
