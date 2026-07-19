from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias

from integrity_agent.core.evidence.scope import FindingScope, scope_of


BilingualText: TypeAlias = str | dict[str, str]


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def resolve_bilingual_string(data: BilingualText | None, locale: str = "en") -> str:
    """Resolve a plain string or {"en": "...", "zh": "..."} mapping."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return str(data)
    if locale in data and data[locale]:
        return str(data[locale])
    if "en" in data and data["en"]:
        return str(data["en"])
    for value in data.values():
        if value:
            return str(value)
    return ""


def resolve_bilingual_list(
    items: list[BilingualText] | None,
    locale: str = "en",
) -> list[str]:
    if not items:
        return []
    return [resolve_bilingual_string(item, locale) for item in items]


@dataclass(frozen=True)
class EvidenceItem:
    source: str
    location: str
    quote: str | None = None
    page: int | None = None
    figure: str | None = None
    table: str | None = None
    row: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "source": self.source,
            "location": self.location,
        }
        optional = {
            "quote": self.quote,
            "page": self.page,
            "figure": self.figure,
            "table": self.table,
            "row": self.row,
            "metadata": self.metadata or None,
        }
        record.update({key: value for key, value in optional.items() if value is not None})
        return record


@dataclass(frozen=True)
class ManualVerification:
    needed: bool
    requests: list[BilingualText] = field(default_factory=list)

    def __iter__(self):
        return iter(self.requests)

    def __contains__(self, item: object) -> bool:
        return item in self.requests

    def __len__(self) -> int:
        return len(self.requests)

    def requests_for(self, locale: str = "en") -> list[str]:
        return resolve_bilingual_list(self.requests, locale)

    def to_record(self, locale: str | None = None) -> dict[str, Any]:
        return {
            "needed": self.needed,
            "requests": self.requests_for(locale) if locale else list(self.requests),
        }


@dataclass(frozen=True)
class Finding:
    finding_id: str
    type: str
    title: BilingualText
    risk: RiskLevel
    summary: BilingualText
    evidence: list[EvidenceItem]
    manual_verification: ManualVerification
    safe_report_language: BilingualText | None = None
    finding_category: str = "general"
    false_positive_risks: list[BilingualText] = field(default_factory=list)
    alternative_explanations: list[BilingualText] = field(default_factory=list)
    limitations: list[BilingualText] | dict[str, str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    scope: FindingScope = FindingScope.RESEARCH_INTEGRITY

    def title_for(self, locale: str = "en") -> str:
        return resolve_bilingual_string(self.title, locale)

    def summary_for(self, locale: str = "en") -> str:
        return resolve_bilingual_string(self.summary, locale)

    def to_ledger_record(self, locale: str | None = None) -> dict[str, Any]:
        limitations: Any
        if locale and isinstance(self.limitations, list):
            limitations = resolve_bilingual_list(self.limitations, locale)
        elif locale and isinstance(self.limitations, dict):
            limitations = resolve_bilingual_string(self.limitations, locale)
        else:
            limitations = list(self.limitations) if isinstance(self.limitations, list) else dict(self.limitations)

        record = {
            "finding_id": self.finding_id,
            "scope": scope_of(self).value,
            "finding_category": self.finding_category,
            "type": self.type,
            "title": self.title_for(locale) if locale else self.title,
            "summary": self.summary_for(locale) if locale else self.summary,
            "risk": self.risk.value,
            "risk_level": self.risk.value,
            "needs_manual_review": self.manual_verification.needed,
            "evidence": [item.to_record() for item in self.evidence],
            "manual_verification": self.manual_verification.to_record(locale),
            "false_positive_risks": (
                resolve_bilingual_list(self.false_positive_risks, locale)
                if locale
                else list(self.false_positive_risks)
            ),
            "alternative_explanations": (
                resolve_bilingual_list(self.alternative_explanations, locale)
                if locale
                else list(self.alternative_explanations)
            ),
            "limitations": limitations,
            "provenance": dict(self.provenance),
        }
        if self.safe_report_language is not None:
            record["safe_report_language"] = (
                resolve_bilingual_string(self.safe_report_language, locale)
                if locale
                else self.safe_report_language
            )
        rule_id = self.provenance.get("rule_id")
        if rule_id:
            record["rule_id"] = rule_id
        return record

    def to_json_line(self) -> str:
        return json.dumps(self.to_ledger_record(), ensure_ascii=False, sort_keys=True)
