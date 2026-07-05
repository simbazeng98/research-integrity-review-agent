from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageManifestItem:
    """Represents a single image item parsed during image intake."""
    image_id: str
    source_file: str
    relative_path: str
    file_name: str
    file_ext: str
    file_size_bytes: int
    sha256: str
    width: int
    height: int
    mode: str
    format: str
    page_number: int | None = None
    pdf_xref: int | None = None
    extraction_method: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "source_file": self.source_file,
            "relative_path": self.relative_path,
            "file_name": self.file_name,
            "file_ext": self.file_ext,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "mode": self.mode,
            "format": self.format,
            "page_number": self.page_number,
            "pdf_xref": self.pdf_xref,
            "extraction_method": self.extraction_method,
            "warnings": self.warnings,
        }


@dataclass
class ImagePackageManifest:
    """Manifest representing all images collected in a package/run."""
    package_path: str
    total_images: int
    items: list[ImageManifestItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_path": self.package_path,
            "total_images": self.total_images,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class ImageEvidenceFinding:
    """Represents an image evidence risk signal (e.g. duplicate images)."""
    finding_id: str
    rule_id: str
    risk_level: str
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    safe_report_language: str = ""
    alternative_explanations: list[str] = field(default_factory=list)
    manual_verification: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "risk_level": self.risk_level,
            "evidence_items": self.evidence_items,
            "safe_report_language": self.safe_report_language,
            "alternative_explanations": self.alternative_explanations,
            "manual_verification": self.manual_verification,
            "metadata": self.metadata,
        }
