from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from integrity_agent.core.evidence.schema import Finding


@dataclass(frozen=True)
class DomainColumnMatch:
    domain_id: str
    score: float
    matched_fields: dict[str, str]


class BaseDomainPlugin(ABC):
    @abstractmethod
    def get_domain_id(self) -> str:
        """Return a stable domain id such as clinical or biomedical."""

    @abstractmethod
    def get_field_mappings(self) -> dict[str, list[str]]:
        """Map canonical metric field names to regex patterns."""

    @abstractmethod
    def normalize_units(
        self,
        field_name: str,
        value: float,
        raw_unit: str,
    ) -> tuple[float, list[str]]:
        """Normalize values to the domain default unit."""

    @abstractmethod
    def build_metric_rows(self, raw_tables: list[Any]) -> list[Any]:
        """Build domain MetricRow instances from generic table data."""

    @abstractmethod
    def run_detectors(
        self,
        rows: list[Any],
        options: dict[str, Any] | None = None,
    ) -> list[Finding]:
        """Run domain detectors and return unified Finding objects."""

    def match_columns(self, columns: list[str]) -> DomainColumnMatch:
        matched: dict[str, str] = {}
        normalized_columns = [(column, column.strip().lower()) for column in columns]
        for canonical, patterns in self.get_field_mappings().items():
            for original, normalized in normalized_columns:
                if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
                    matched[canonical] = original
                    break
        total = max(1, len(self.get_field_mappings()))
        return DomainColumnMatch(
            domain_id=self.get_domain_id(),
            score=round(len(matched) / total, 4),
            matched_fields=matched,
        )


class SkeletonDomainPlugin(BaseDomainPlugin):
    domain_id: str = ""
    field_mappings: dict[str, list[str]] = {}

    def get_domain_id(self) -> str:
        return self.domain_id

    def get_field_mappings(self) -> dict[str, list[str]]:
        return self.field_mappings

    def normalize_units(
        self,
        field_name: str,
        value: float,
        raw_unit: str,
    ) -> tuple[float, list[str]]:
        return value, []

    def build_metric_rows(self, raw_tables: list[Any]) -> list[Any]:
        return []

    def run_detectors(
        self,
        rows: list[Any],
        options: dict[str, Any] | None = None,
    ) -> list[Finding]:
        return []
