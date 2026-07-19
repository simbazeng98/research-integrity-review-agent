from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from integrity_agent.core.safety import find_runtime_safety_issues


class VersionSourceType(str, Enum):
    """Source categories ordered by authority for publication *status* only.

    The order does not determine whether a scientific claim is true. It only
    controls how an observed mismatch may be labelled after counter-evidence is
    linked to it.
    """

    PUBLISHER_CORRECTION = "publisher_correction"
    PUBLISHER_RETRACTION = "publisher_retraction"
    PUBLISHER_UPDATE = "publisher_update"
    CURRENT_PUBLISHER_ARTICLE = "current_publisher_article"
    CURRENT_PUBLISHER_SI = "current_publisher_si"
    ORIGINAL_PUBLIC_VERSION = "original_public_version"
    AUTHOR_RESPONSE = "author_response"
    REVISED_DRAFT = "revised_draft"
    THIRD_PARTY_SOCIAL = "third_party_social"


class ResolutionStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_EXPLAINED = "partially_explained"
    RESOLVED_BY_VERSION = "resolved_by_version"
    FORMALLY_CORRECTED = "formally_corrected"
    UNRESOLVED = "unresolved"


_SOURCE_PRECEDENCE: dict[VersionSourceType, int] = {
    VersionSourceType.PUBLISHER_CORRECTION: 1,
    VersionSourceType.PUBLISHER_RETRACTION: 1,
    VersionSourceType.PUBLISHER_UPDATE: 1,
    VersionSourceType.CURRENT_PUBLISHER_ARTICLE: 2,
    VersionSourceType.CURRENT_PUBLISHER_SI: 2,
    VersionSourceType.ORIGINAL_PUBLIC_VERSION: 3,
    VersionSourceType.AUTHOR_RESPONSE: 4,
    VersionSourceType.REVISED_DRAFT: 4,
    VersionSourceType.THIRD_PARTY_SOCIAL: 5,
}


def source_precedence(source_type: VersionSourceType | str) -> int:
    """Return status-authority precedence (lower is more authoritative)."""

    return _SOURCE_PRECEDENCE[VersionSourceType(source_type)]


PUBLISHER_NOTICE_TYPES = frozenset(
    {
        VersionSourceType.PUBLISHER_CORRECTION,
        VersionSourceType.PUBLISHER_RETRACTION,
        VersionSourceType.PUBLISHER_UPDATE,
    }
)
CURRENT_PUBLISHER_TYPES = frozenset(
    {
        VersionSourceType.CURRENT_PUBLISHER_ARTICLE,
        VersionSourceType.CURRENT_PUBLISHER_SI,
    }
)
PUBLISHER_SOURCE_TYPES = PUBLISHER_NOTICE_TYPES | CURRENT_PUBLISHER_TYPES
NON_PUBLISHER_COUNTER_TYPES = frozenset(
    {
        VersionSourceType.AUTHOR_RESPONSE,
        VersionSourceType.REVISED_DRAFT,
        VersionSourceType.THIRD_PARTY_SOCIAL,
    }
)


_SOURCE_TYPE_ALIASES = {
    "correction": VersionSourceType.PUBLISHER_CORRECTION.value,
    "retraction": VersionSourceType.PUBLISHER_RETRACTION.value,
    "update": VersionSourceType.PUBLISHER_UPDATE.value,
    "publisher_article": VersionSourceType.CURRENT_PUBLISHER_ARTICLE.value,
    "publisher_current_article": VersionSourceType.CURRENT_PUBLISHER_ARTICLE.value,
    "current_article": VersionSourceType.CURRENT_PUBLISHER_ARTICLE.value,
    "publisher_si": VersionSourceType.CURRENT_PUBLISHER_SI.value,
    "publisher_current_si": VersionSourceType.CURRENT_PUBLISHER_SI.value,
    "current_si": VersionSourceType.CURRENT_PUBLISHER_SI.value,
    "original_version": VersionSourceType.ORIGINAL_PUBLIC_VERSION.value,
    "social": VersionSourceType.THIRD_PARTY_SOCIAL.value,
    "social_commentary": VersionSourceType.THIRD_PARTY_SOCIAL.value,
}


class VersionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_type: VersionSourceType
    source_url: str = Field(min_length=1)
    observed_at: str = Field(min_length=4)
    status: str = Field(min_length=1)
    resolution_status: ResolutionStatus | None = None
    related_finding_ids: list[str] = Field(default_factory=list)
    related_claim_ids: list[str] = Field(default_factory=list)
    resolves_event_ids: list[str] = Field(default_factory=list)
    resolves_finding_ids: list[str] = Field(default_factory=list)
    supersedes_versions: list[str] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_compatible_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "source_version" not in normalized and "version_id" in normalized:
            normalized["source_version"] = normalized.pop("version_id")
        if "source_url" not in normalized and "source" in normalized:
            normalized["source_url"] = normalized.pop("source")
        raw_type = normalized.get("source_type")
        if isinstance(raw_type, str):
            normalized["source_type"] = _SOURCE_TYPE_ALIASES.get(
                raw_type.strip().lower(), raw_type.strip().lower()
            )
        return normalized

    @field_validator(
        "event_id",
        "source_version",
        "source_url",
        "status",
        mode="before",
    )
    @classmethod
    def require_nonempty_string(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value.strip()

    @field_validator("observed_at", mode="before")
    @classmethod
    def normalize_observed_at(cls, value: Any) -> str:
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        if not isinstance(value, str) or not value.strip():
            raise ValueError("observed_at must be an ISO-8601 date or timestamp")
        candidate = value.strip()
        try:
            datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "observed_at must be an ISO-8601 date or timestamp"
            ) from exc
        return candidate

    @field_validator(
        "related_finding_ids",
        "related_claim_ids",
        "resolves_event_ids",
        "resolves_finding_ids",
        "supersedes_versions",
    )
    @classmethod
    def require_unique_nonempty_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("link identifiers must be non-empty strings")
            item = item.strip()
            if item not in normalized:
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def enforce_resolution_authority(self) -> VersionEvent:
        if (
            self.source_type in NON_PUBLISHER_COUNTER_TYPES
            and self.resolution_status
            in {
                ResolutionStatus.RESOLVED_BY_VERSION,
                ResolutionStatus.FORMALLY_CORRECTED,
            }
        ):
            if self.source_type is VersionSourceType.AUTHOR_RESPONSE:
                label = "author response"
            elif self.source_type is VersionSourceType.REVISED_DRAFT:
                label = "revised draft"
            else:
                label = "third-party social source"
            raise ValueError(
                f"{label} can be counter-evidence or partially explained, "
                "but cannot establish publisher resolution"
            )
        if (
            self.resolution_status is ResolutionStatus.FORMALLY_CORRECTED
            and self.source_type not in PUBLISHER_NOTICE_TYPES
        ):
            raise ValueError(
                "formally_corrected requires a publisher correction, retraction, or update"
            )
        if (
            self.resolution_status is ResolutionStatus.RESOLVED_BY_VERSION
            and self.source_type not in PUBLISHER_SOURCE_TYPES
        ):
            raise ValueError("resolved_by_version requires publisher-hosted evidence")
        return self

    @property
    def is_publisher_evidence(self) -> bool:
        return self.source_type in PUBLISHER_SOURCE_TYPES


class VersionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str = "1"
    target_doi: str = Field(min_length=5)
    events: list[VersionEvent] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_timeline_key(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "events" not in normalized and "version_timeline" in normalized:
            normalized["events"] = normalized.pop("version_timeline")
        return normalized

    @field_validator("manifest_version", mode="before")
    @classmethod
    def normalize_manifest_version(cls, value: Any) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("manifest_version must not be empty")
        return value

    @field_validator("target_doi")
    @classmethod
    def validate_target_doi(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.startswith("https://doi.org/"):
            normalized = normalized.removeprefix("https://doi.org/")
        elif normalized.startswith("doi:"):
            normalized = normalized.removeprefix("doi:").strip()
        if not re.fullmatch(r"10\.\d{4,9}/\S+", normalized):
            raise ValueError("target_doi must be a DOI")
        return normalized

    @model_validator(mode="after")
    def validate_event_contract(self) -> VersionManifest:
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("version events must have unique event_id values")

        issues = find_runtime_safety_issues(self.model_dump(mode="json"))
        if issues:
            raise ValueError(
                "unsafe public manifest content: " + "; ".join(sorted(set(issues)))
            )
        return self


def load_version_manifest(path: Path | str) -> VersionManifest:
    """Load a local YAML manifest without network access."""

    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Version manifest not found: {manifest_path}")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("version manifest must contain a YAML mapping")
    return VersionManifest.model_validate(raw)


__all__ = [
    "CURRENT_PUBLISHER_TYPES",
    "NON_PUBLISHER_COUNTER_TYPES",
    "PUBLISHER_NOTICE_TYPES",
    "PUBLISHER_SOURCE_TYPES",
    "ResolutionStatus",
    "VersionEvent",
    "VersionManifest",
    "VersionSourceType",
    "load_version_manifest",
    "source_precedence",
]
