from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CrossrefUpdateItem:
    doi: str  # The target article's DOI
    update_type: str  # e.g., 'retraction', 'correction', 'expression_of_concern', etc.
    source: str  # 'updated-by' or 'update-to'
    label: str | None  # label text from Crossref (e.g., 'Retraction notice')
    updated_date: str | None  # date formatted as YYYY-MM-DD
    related_doi: str  # the DOI of the notice itself
    raw_field: dict[str, Any]  # raw dictionary representation from Crossref


@dataclass(frozen=True)
class MetadataUpdateResult:
    doi: str
    status: str  # retraction, correction, expression_of_concern, reinstatement, no_known_update, metadata_unavailable
    updates: list[CrossrefUpdateItem] = field(default_factory=list)


def _parse_date(date_dict: dict[str, Any] | None) -> str | None:
    """Format Crossref date-parts as YYYY-MM-DD, YYYY-MM, or YYYY."""
    if not date_dict or "date-parts" not in date_dict:
        return None
    try:
        parts_list = date_dict["date-parts"]
        if not parts_list or not isinstance(parts_list, list):
            return None
        parts = parts_list[0]
        if not parts or not isinstance(parts, list):
            return None
        
        valid_parts = [p for p in parts if p is not None]
        if len(valid_parts) >= 3:
            return f"{valid_parts[0]}-{int(valid_parts[1]):02d}-{int(valid_parts[2]):02d}"
        elif len(valid_parts) == 2:
            return f"{valid_parts[0]}-{int(valid_parts[1]):02d}"
        elif len(valid_parts) == 1:
            return f"{valid_parts[0]}"
    except Exception:
        pass
    return None


def parse_crossref_updates(work_json: dict[str, Any]) -> MetadataUpdateResult:
    """Parse Crossref metadata and identify update/retraction signals.

    Normalizes updates from both `updated-by` and `update-to` fields.
    """
    if not work_json or "message" not in work_json:
        return MetadataUpdateResult(doi="unknown", status="metadata_unavailable")

    message = work_json["message"]
    doi = str(message.get("DOI", "unknown")).lower()

    updates: list[CrossrefUpdateItem] = []
    seen_related: set[str] = set()

    # 1. Parse 'updated-by'
    for item in message.get("updated-by", []):
        raw_type = str(item.get("type", "")).strip().lower()
        if not raw_type:
            continue
        
        related_doi = str(item.get("DOI", "unknown")).strip().lower()
        if related_doi != "unknown" and related_doi in seen_related:
            continue
        if related_doi != "unknown":
            seen_related.add(related_doi)

        # Map raw Crossref update type
        if "retraction" in raw_type or "withdrawal" in raw_type:
            update_type = "retraction"
        elif "concern" in raw_type:
            update_type = "expression_of_concern"
        elif "reinstatement" in raw_type:
            update_type = "reinstatement"
        else:
            update_type = "correction"

        updates.append(
            CrossrefUpdateItem(
                doi=doi,
                update_type=update_type,
                source="updated-by",
                label=item.get("label"),
                updated_date=_parse_date(item.get("updated")),
                related_doi=related_doi,
                raw_field=item,
            )
        )

    # 2. Parse 'update-to' (in case the record fetched is the update notice itself)
    for item in message.get("update-to", []):
        raw_type = str(item.get("type", "")).strip().lower()
        if not raw_type:
            continue

        related_doi = str(item.get("DOI", "unknown")).strip().lower()
        if related_doi != "unknown" and related_doi in seen_related:
            continue
        if related_doi != "unknown":
            seen_related.add(related_doi)

        if "retraction" in raw_type or "withdrawal" in raw_type:
            update_type = "retraction"
        elif "concern" in raw_type:
            update_type = "expression_of_concern"
        elif "reinstatement" in raw_type:
            update_type = "reinstatement"
        else:
            update_type = "correction"

        updates.append(
            CrossrefUpdateItem(
                doi=doi,
                update_type=update_type,
                source="update-to",
                label=item.get("label"),
                updated_date=_parse_date(item.get("updated")),
                related_doi=related_doi,
                raw_field=item,
            )
        )

    # 3. Determine overall status based on priority
    # Reinstatement > Retraction > Expression of Concern > Correction > No known update
    types_found = {u.update_type for u in updates}
    
    if "reinstatement" in types_found:
        status = "reinstatement"
    elif "retraction" in types_found:
        status = "retraction"
    elif "expression_of_concern" in types_found:
        status = "expression_of_concern"
    elif "correction" in types_found:
        status = "correction"
    else:
        status = "no_known_update"

    return MetadataUpdateResult(doi=doi, status=status, updates=updates)
