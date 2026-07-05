from __future__ import annotations

import csv
from pathlib import Path

from integrity_agent.core.intake.batch_schema import LiteratureItem
from integrity_agent.core.metadata.doi import normalize_doi


def parse_doi_list(file_path: Path) -> list[LiteratureItem]:
    """Parse DOI strings from text files (.txt) or spreadsheets (.csv).

    Supports invalid DOIs by logging warnings on items without crashing.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    items: list[LiteratureItem] = []
    source_file = file_path.name
    ext = file_path.suffix.lower()

    if ext == ".txt":
        content = file_path.read_text(encoding="utf-8")
        for idx, line in enumerate(content.splitlines(), 1):
            raw = line.strip()
            if not raw:
                continue

            item_id = f"txt-L{idx}"
            warnings: list[str] = []
            normalized = None
            try:
                normalized = normalize_doi(raw)
            except ValueError as e:
                warnings.append(f"Invalid DOI format: {raw} ({e})")

            items.append(
                LiteratureItem(
                    item_id=item_id,
                    source_file=source_file,
                    source_format="txt",
                    doi=raw,
                    normalized_doi=normalized,
                    warnings=warnings,
                )
            )

    elif ext == ".csv":
        with file_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Prioritize DOI columns
            doi_col = None
            for key in ["doi", "doi_url", "doi_link", "doi-url", "doi-link", "identifier"]:
                for h in headers:
                    if h.lower().strip() == key:
                        doi_col = h
                        break
                if doi_col:
                    break

            if not doi_col:
                for h in headers:
                    if "doi" in h.lower():
                        doi_col = h
                        break

            if not doi_col and headers:
                doi_col = headers[0]

            if not doi_col:
                return []

            for idx, row in enumerate(reader, 1):
                raw = row.get(doi_col, "")
                if raw is None:
                    raw = ""
                raw = raw.strip()
                if not raw:
                    continue

                item_id = f"csv-R{idx}"

                # Extract optional fields if available
                title = None
                for k in ["title", "paper_title", "article_title"]:
                    for h in headers:
                        if h.lower().strip() == k:
                            title = row.get(h)
                            break
                    if title:
                        break

                year = None
                for k in ["year", "date", "issued"]:
                    for h in headers:
                        if h.lower().strip() == k:
                            year = row.get(h)
                            break
                    if year:
                        break

                journal = None
                for k in ["journal", "container-title", "publication"]:
                    for h in headers:
                        if h.lower().strip() == k:
                            journal = row.get(h)
                            break
                    if journal:
                        break

                warnings = []
                normalized = None
                try:
                    normalized = normalize_doi(raw)
                except ValueError as e:
                    warnings.append(f"Invalid DOI format: {raw} ({e})")

                items.append(
                    LiteratureItem(
                        item_id=item_id,
                        source_file=source_file,
                        source_format="csv",
                        doi=raw,
                        normalized_doi=normalized,
                        title=title,
                        year=year,
                        journal=journal,
                        warnings=warnings,
                    )
                )

    else:
        raise ValueError(f"Unsupported format for DOI list: {ext}")

    return items
