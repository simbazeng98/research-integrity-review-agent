from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


BilingualText: TypeAlias = str | dict[str, str]
RiskLevelValue: TypeAlias = Literal["low", "medium", "high"]


class EvidenceLocation(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    source: str = Field(min_length=1)
    location: str = Field(min_length=1)
    quote: str | None = None
    page: int | None = None
    figure: str | None = None
    table: str | None = None
    row: str | int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationQuestion(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    text: BilingualText
    evidence_location: str | None = None


class BenignAlternative(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    text: BilingualText
    review_note: str | None = None


class ManualVerification(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    needed: bool
    requests: list[BilingualText] = Field(default_factory=list)


class ReportLanguageGuard(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    safe_report_language: BilingualText | None = None
    forbidden_verdict_phrases_blocked: bool = True
    requires_manual_verification_language: bool = True


class RiskSignal(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    risk_level: RiskLevelValue
    rule_id: str | None = None
    workflow_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class EvidenceRecord(BaseModel):
    """Machine-readable contract for JSONL evidence-ledger findings.

    The contract keeps core evidence-review fields mandatory while allowing
    module-specific extensions such as image hashes, table IDs, or PV metrics.
    """

    model_config = ConfigDict(extra="allow", strict=True)

    finding_id: str = Field(min_length=1)
    finding_category: str = "general"
    type: str | None = None
    title: BilingualText | None = None
    summary: BilingualText | None = None
    risk: RiskLevelValue
    risk_level: RiskLevelValue
    needs_manual_review: bool | None = None
    evidence: list[EvidenceLocation] = Field(default_factory=list)
    manual_verification: ManualVerification
    false_positive_risks: list[BilingualText] = Field(default_factory=list)
    alternative_explanations: list[BilingualText] = Field(default_factory=list)
    limitations: list[BilingualText] | BilingualText = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    rule_id: str | None = None
    safe_report_language: BilingualText | None = None
    risk_signal: RiskSignal | None = None
    report_language_guard: ReportLanguageGuard | None = None
    verification_questions: list[VerificationQuestion] = Field(default_factory=list)
    benign_alternatives: list[BenignAlternative] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_ledger_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "finding_id" not in normalized and "candidate_id" in normalized:
            normalized["finding_id"] = normalized["candidate_id"]
        if "risk" not in normalized and "risk_level" in normalized:
            normalized["risk"] = normalized["risk_level"]
        if "risk_level" not in normalized and "risk" in normalized:
            normalized["risk_level"] = normalized["risk"]
        if "evidence" not in normalized and "evidence_items" in normalized:
            normalized["evidence"] = normalized["evidence_items"]
        if "evidence" not in normalized:
            normalized["evidence"] = _infer_evidence_locations(normalized)
        else:
            parent_source = (
                normalized.get("source_file")
                or normalized.get("relative_path")
                or normalized.get("relative_path_a")
            )
            normalized["evidence"] = [
                _normalize_evidence_location(item, parent_source=parent_source)
                for item in normalized["evidence"]
            ]
        manual_verification = normalized.get("manual_verification")
        if isinstance(manual_verification, list):
            normalized["manual_verification"] = {
                "needed": bool(manual_verification),
                "requests": manual_verification,
            }
        if "summary" not in normalized and "safe_report_language" in normalized:
            normalized["summary"] = normalized["safe_report_language"]
        if "type" not in normalized and "rule_id" in normalized:
            normalized["type"] = normalized["rule_id"]
        if "title" not in normalized:
            normalized["title"] = normalized.get("type") or normalized.get("rule_id")
        if "finding_category" not in normalized and "rule_id" in normalized:
            normalized["finding_category"] = "rule"
        return normalized

    @model_validator(mode="after")
    def require_traceable_review_fields(self) -> EvidenceRecord:
        if not self.evidence:
            raise ValueError("evidence ledger record must include at least one evidence location")
        if self.needs_manual_review is not None and self.needs_manual_review != self.manual_verification.needed:
            raise ValueError("needs_manual_review must match manual_verification.needed")
        if self.summary is None and self.safe_report_language is None:
            raise ValueError("record must include summary or safe_report_language")
        return self


def evidence_record_json_schema() -> dict[str, Any]:
    return EvidenceRecord.model_json_schema()


def _normalize_evidence_location(item: Any, *, parent_source: Any = None) -> Any:
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    source = (
        normalized.get("source")
        or normalized.get("relative_path")
        or normalized.get("path")
        or normalized.get("source_file")
        or normalized.get("file_name")
        or normalized.get("image_id")
        or parent_source
    )
    location = (
        normalized.get("location")
        or normalized.get("figure")
        or normalized.get("table")
        or normalized.get("row_range")
        or normalized.get("image_id")
        or normalized.get("file_name")
        or normalized.get("relative_path")
        or source
    )
    if source is not None:
        normalized["source"] = str(source)
    if location is not None:
        normalized["location"] = str(location)
    return normalized


def _infer_evidence_locations(record: dict[str, Any]) -> list[dict[str, Any]]:
    if record.get("relative_path_a") and record.get("relative_path_b"):
        source = str(record["relative_path_a"])
        other = str(record["relative_path_b"])
        return [
            {
                "source": source,
                "location": f"{source} vs {other}",
                "metadata": {
                    key: value
                    for key, value in record.items()
                    if key
                    in {
                        "image_id_a",
                        "image_id_b",
                        "relative_path_a",
                        "relative_path_b",
                        "hash_method",
                        "hamming_distance",
                        "threshold",
                    }
                },
            }
        ]
    if record.get("source_file"):
        location_parts = [
            str(value)
            for value in (
                record.get("table_id"),
                record.get("row_range"),
                record.get("rule_id"),
            )
            if value
        ]
        return [
            {
                "source": str(record["source_file"]),
                "location": "; ".join(location_parts) or str(record["source_file"]),
            }
        ]
    if record.get("relative_path"):
        return [
            {
                "source": str(record["relative_path"]),
                "location": str(record.get("location") or record["relative_path"]),
            }
        ]
    return []
