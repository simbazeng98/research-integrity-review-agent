from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


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
    requests: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "needed": self.needed,
            "requests": list(self.requests),
        }


@dataclass(frozen=True)
class Finding:
    finding_id: str
    type: str
    title: str
    risk: RiskLevel
    summary: str
    evidence: list[EvidenceItem]
    manual_verification: ManualVerification
    false_positive_risks: list[str] = field(default_factory=list)
    alternative_explanations: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_ledger_record(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "type": self.type,
            "title": self.title,
            "summary": self.summary,
            "risk": self.risk.value,
            "needs_manual_review": self.manual_verification.needed,
            "evidence": [item.to_record() for item in self.evidence],
            "manual_verification": self.manual_verification.to_record(),
            "false_positive_risks": list(self.false_positive_risks),
            "alternative_explanations": list(self.alternative_explanations),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_ledger_record(), ensure_ascii=False, sort_keys=True)
