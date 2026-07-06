from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from integrity_agent.core.evidence.schema import (
    BilingualText,
    resolve_bilingual_list,
    resolve_bilingual_string,
)


@dataclass(frozen=True)
class RuleInputRequirement:
    input_required: list[str]
    fields_required: list[str]


@dataclass(frozen=True)
class DetectorRule:
    rule_id: str
    input_requirement: RuleInputRequirement
    risk_signal: str
    manual_verification: list[str]
    false_positive_risks: list[str]
    safe_report_language: str
    runtime_status: str
    execution_mode: str
    toy_fixture: str | None
    detector_module: str | None
    detector_function: str | None
    requires_network: bool
    requires_private_data: bool
    risk_ceiling: str
    status: str = "draft_spec_only"
    linked_cases: list[str] = field(default_factory=list)
    detection_idea: list[str] = field(default_factory=list)
    traceability: list[str] = field(default_factory=list)
    source_path: Path | None = None
    accepted_input_types: list[str] = field(default_factory=list)
    minimum_sample_size: int | None = None
    field_requirements: list[str] = field(default_factory=list)
    known_false_positive_contexts: list[str] = field(default_factory=list)
    title: dict[str, str] = field(default_factory=dict)
    description: dict[str, str] = field(default_factory=dict)
    risk_signal_i18n: BilingualText | None = None
    manual_verification_i18n: list[BilingualText] = field(default_factory=list)
    false_positive_risks_i18n: list[BilingualText] = field(default_factory=list)
    safe_report_language_i18n: BilingualText | None = None

    def title_for(self, locale: str = "en") -> str:
        return resolve_bilingual_string(self.title or self.rule_id, locale)

    def description_for(self, locale: str = "en") -> str:
        return resolve_bilingual_string(self.description or "", locale)

    def risk_signal_for(self, locale: str = "en") -> str:
        return resolve_bilingual_string(self.risk_signal_i18n or self.risk_signal, locale)

    def manual_verification_for(self, locale: str = "en") -> list[str]:
        return resolve_bilingual_list(
            self.manual_verification_i18n or self.manual_verification,
            locale,
        )

    def false_positive_risks_for(self, locale: str = "en") -> list[str]:
        return resolve_bilingual_list(
            self.false_positive_risks_i18n or self.false_positive_risks,
            locale,
        )

    def safe_report_language_for(self, locale: str = "en") -> str:
        return resolve_bilingual_string(
            self.safe_report_language_i18n or self.safe_report_language,
            locale,
        )


@dataclass(frozen=True)
class RuleExecutionResult:
    finding_id: str
    rule_id: str
    risk_level: str
    evidence_items: list[dict[str, Any]]
    manual_verification: dict[str, Any]
    false_positive_risks: list[str]
    safe_report_language: str
    alternative_explanations: list[str] = field(default_factory=list)
    missing_verification_materials: list[str] = field(default_factory=list)
    suggested_verification_questions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "risk_level": self.risk_level,
            "evidence_items": self.evidence_items,
            "manual_verification": self.manual_verification,
            "false_positive_risks": self.false_positive_risks,
            "safe_report_language": self.safe_report_language,
            "alternative_explanations": self.alternative_explanations,
            "missing_verification_materials": self.missing_verification_materials,
            "suggested_verification_questions": self.suggested_verification_questions,
            "limitations": self.limitations,
            "metadata": self.metadata,
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_record(), ensure_ascii=False, sort_keys=True)
