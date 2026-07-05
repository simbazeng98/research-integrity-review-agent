from __future__ import annotations

from dataclasses import dataclass, field


class BatchItemStatus:
    """Status indicating how the item was processed during intake."""
    VALID = "valid"
    INVALID_DOI = "invalid_doi"
    DUPLICATE = "duplicate"
    MISSING_DOI = "missing_doi"


@dataclass
class LiteratureItem:
    """A single literature item parsed during batch intake."""
    item_id: str
    source_file: str
    source_format: str
    doi: str | None = None
    normalized_doi: str | None = None
    title: str | None = None
    year: str | None = None
    journal: str | None = None
    metadata_status: str = "offline"  # success, failed, rate_limited, offline
    crossref_update_status: str = "metadata_unavailable"  # retraction, correction, etc.
    warnings: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    reference_type: str | None = None
    raw_tags: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, any]:
        return {
            "item_id": self.item_id,
            "source_file": self.source_file,
            "source_format": self.source_format,
            "doi": self.doi,
            "normalized_doi": self.normalized_doi,
            "title": self.title,
            "year": self.year,
            "journal": self.journal,
            "metadata_status": self.metadata_status,
            "crossref_update_status": self.crossref_update_status,
            "warnings": self.warnings,
            "authors": self.authors,
            "reference_type": self.reference_type,
            "raw_tags": self.raw_tags,
        }


@dataclass
class BatchIntakeResult:
    """Consolidated summary of a batch intake run."""
    source_file: str
    source_format: str
    total_items: int
    valid_dois: int
    duplicate_dois: int
    lookup_mode: str  # "offline" or "allow-network"
    items: list[LiteratureItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, any]:
        return {
            "source_file": self.source_file,
            "source_format": self.source_format,
            "total_items": self.total_items,
            "valid_dois": self.valid_dois,
            "duplicate_dois": self.duplicate_dois,
            "lookup_mode": self.lookup_mode,
            "items": [item.to_dict() for item in self.items],
        }
