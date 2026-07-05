from __future__ import annotations

import re
from pathlib import Path

from integrity_agent.core.intake.batch_schema import LiteratureItem
from integrity_agent.core.metadata.doi import normalize_doi


def parse_ris(file_path: Path) -> list[LiteratureItem]:
    """Parse citation metadata from a RIS (.ris) export file."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    lines = file_path.read_text(encoding="utf-8").splitlines()
    items: list[LiteratureItem] = []
    source_file = file_path.name

    current_record: dict[str, list[str]] = {}
    record_idx = 1

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match tag pattern: tag must be 2 characters (capital letters or numbers)
        # followed by two spaces or space/hyphen/space, e.g. "TY  - "
        match = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", line)
        if not match:
            continue

        tag = match.group(1).upper()
        value = match.group(2).strip()

        if tag == "TY":
            # If we already have a record being built, finalize it (e.g. if ER was missing)
            if current_record:
                item = _build_item_from_ris_record(current_record, f"ris-R{record_idx}", source_file)
                items.append(item)
                record_idx += 1
            current_record = {"TY": [value]}
        elif tag == "ER":
            if current_record:
                item = _build_item_from_ris_record(current_record, f"ris-R{record_idx}", source_file)
                items.append(item)
                record_idx += 1
                current_record = {}
        else:
            if current_record is not None:
                if tag not in current_record:
                    current_record[tag] = []
                current_record[tag].append(value)

    # Finalize any dangling record
    if current_record and "TY" in current_record:
        item = _build_item_from_ris_record(current_record, f"ris-R{record_idx}", source_file)
        items.append(item)

    return items


def _build_item_from_ris_record(
    record: dict[str, list[str]],
    item_id: str,
    source_file: str,
) -> LiteratureItem:
    # 1. DOI from DO tag
    doi_list = record.get("DO", [])
    doi_val = doi_list[0].strip() if doi_list else None

    # 2. Title from TI or T1 tags
    title_list = record.get("TI", []) or record.get("T1", [])
    title_val = title_list[0].strip() if title_list else None

    # 3. Journal from JO, JF, T2 tags
    journal_list = record.get("JO", []) or record.get("JF", []) or record.get("T2", [])
    journal_val = journal_list[0].strip() if journal_list else None

    # 4. Year from PY or Y1 tags
    year_list = record.get("PY", []) or record.get("Y1", [])
    year_val = year_list[0].strip() if year_list else None
    if year_val:
        # Extract the first 4-digit number if full date is specified (e.g., 2026/07/04/)
        year_match = re.match(r"^(\d{4})", year_val)
        if year_match:
            year_val = year_match.group(1)

    # 5. Authors from AU tag (allows repeated lines)
    authors = [a.strip() for a in record.get("AU", [])]

    # 6. Reference Type from TY tag
    ty_list = record.get("TY", [])
    ref_type = ty_list[0].strip() if ty_list else None

    # 7. Retain unrecognized tags
    recognized_tags = {"TY", "ER", "DO", "TI", "T1", "JO", "JF", "T2", "PY", "Y1", "AU"}
    raw_tags = {k: v for k, v in record.items() if k not in recognized_tags}

    warnings: list[str] = []
    normalized = None

    if doi_val:
        try:
            normalized = normalize_doi(doi_val)
        except ValueError as e:
            warnings.append(f"Invalid DOI format: {doi_val} ({e})")
    else:
        warnings.append("Missing DOI for item.")

    return LiteratureItem(
        item_id=item_id,
        source_file=source_file,
        source_format="ris",
        doi=doi_val,
        normalized_doi=normalized,
        title=title_val,
        year=year_val,
        journal=journal_val,
        authors=authors,
        reference_type=ref_type,
        raw_tags=raw_tags,
        warnings=warnings,
    )
