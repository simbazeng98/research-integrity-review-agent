from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)


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


def _risk_from_string(value: str) -> RiskLevel:
    try:
        return RiskLevel(value.lower())
    except ValueError:
        return RiskLevel.LOW


def _image_evidence_item(raw: dict[str, Any]) -> EvidenceItem:
    source = (
        raw.get("source")
        or raw.get("relative_path")
        or raw.get("path")
        or raw.get("file_name")
        or "unknown_image"
    )
    location = raw.get("location") or raw.get("image_id") or raw.get("file_name") or source
    return EvidenceItem(
        source=str(source),
        location=str(location),
        page=raw.get("page_number") or raw.get("page"),
        figure=raw.get("figure"),
        metadata=dict(raw),
    )


@dataclass(frozen=True, init=False)
class ImageEvidenceFinding(Finding):
    """Image risk-signal finding backed by the unified core Finding schema."""
    rule_id: str
    risk_level: str
    evidence_items: list[dict[str, Any]]
    safe_report_language: str
    metadata: dict[str, Any]

    def __init__(
        self,
        finding_id: str,
        rule_id: str,
        risk_level: str,
        evidence_items: list[dict[str, Any]] | None = None,
        safe_report_language: str = "",
        alternative_explanations: list[str] | None = None,
        manual_verification: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        evidence_items = list(evidence_items or [])
        alternative_explanations = list(alternative_explanations or [])
        manual_verification = list(manual_verification or [])
        metadata = dict(metadata or {})
        provenance = dict(metadata)
        provenance["rule_id"] = rule_id

        object.__setattr__(self, "finding_id", finding_id)
        object.__setattr__(self, "type", rule_id)
        object.__setattr__(
            self,
            "title",
            {"en": rule_id.replace("_", " "), "zh": rule_id.replace("_", " ")},
        )
        object.__setattr__(self, "risk", _risk_from_string(risk_level))
        object.__setattr__(
            self,
            "summary",
            {"en": safe_report_language, "zh": safe_report_language},
        )
        object.__setattr__(
            self,
            "evidence",
            [_image_evidence_item(item) for item in evidence_items],
        )
        object.__setattr__(
            self,
            "manual_verification",
            ManualVerification(needed=bool(manual_verification), requests=manual_verification),
        )
        object.__setattr__(self, "finding_category", "image")
        object.__setattr__(self, "false_positive_risks", [])
        object.__setattr__(self, "alternative_explanations", alternative_explanations)
        object.__setattr__(self, "limitations", [])
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "risk_level", risk_level)
        object.__setattr__(self, "evidence_items", evidence_items)
        object.__setattr__(self, "safe_report_language", safe_report_language)
        object.__setattr__(self, "metadata", metadata)

    def to_ledger_record(self, locale: str | None = None) -> dict[str, Any]:
        record = super().to_ledger_record(locale=locale)
        record.update(
            {
                "rule_id": self.rule_id,
                "risk_level": self.risk_level,
                "safe_report_language": self.safe_report_language,
                "evidence_items": list(self.evidence_items),
                "metadata": dict(self.metadata),
            }
        )
        return record

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "risk_level": self.risk_level,
            "evidence_items": self.evidence_items,
            "safe_report_language": self.safe_report_language,
            "alternative_explanations": self.alternative_explanations,
            "manual_verification": list(self.manual_verification.requests),
            "metadata": self.metadata,
        }
