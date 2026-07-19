from __future__ import annotations

from enum import Enum
from typing import Any, Iterable


class FindingScope(str, Enum):
    """Explicit review scope for an evidence-ledger record.

    Scope is supplied by the producing workflow.  It is intentionally not
    inferred from keywords in titles, summaries, or evidence text.
    """

    RESEARCH_INTEGRITY = "research_integrity"
    ENGINEERING_PLAUSIBILITY = "engineering_plausibility"
    UNSUPPORTED_MOTIVE = "unsupported_motive"


def scope_of(record: Any) -> FindingScope:
    """Return an explicit scope, defaulting only legacy records to integrity."""

    if isinstance(record, dict):
        raw_scope = record.get("scope")
    else:
        raw_scope = getattr(record, "scope", None)
    if raw_scope is None:
        return FindingScope.RESEARCH_INTEGRITY
    if isinstance(raw_scope, FindingScope):
        return raw_scope
    try:
        return FindingScope(raw_scope)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(scope.value for scope in FindingScope)
        raise ValueError(f"scope must be one of: {allowed}") from exc


def contributes_to_integrity_mrpi(record: Any) -> bool:
    """Only research-integrity findings contribute to the integrity MRPI."""

    return scope_of(record) is FindingScope.RESEARCH_INTEGRITY


def split_public_records(records: Iterable[Any]) -> tuple[list[Any], list[Any]]:
    """Split public findings into integrity findings and engineering questions.

    Unsupported motive assertions are intentionally omitted.  They are not a
    public finding type and must not be rendered as evidence-ledger findings.
    """

    integrity_findings: list[Any] = []
    engineering_questions: list[Any] = []
    for record in records:
        scope = scope_of(record)
        if scope is FindingScope.RESEARCH_INTEGRITY:
            integrity_findings.append(record)
        elif scope is FindingScope.ENGINEERING_PLAUSIBILITY:
            engineering_questions.append(record)
    return integrity_findings, engineering_questions
