from __future__ import annotations

from typing import Any, Iterable

from integrity_agent.core.evidence.schema import Finding, RiskLevel
from integrity_agent.core.evidence.scope import contributes_to_integrity_mrpi


RISK_WEIGHTS = {
    RiskLevel.HIGH.value: 0.35,
    RiskLevel.MEDIUM.value: 0.15,
    RiskLevel.LOW.value: 0.05,
}

_CLOSED_RESOLUTION_STATUSES = {"resolved_by_version", "formally_corrected"}
_METHOD_CARD_TYPES = {"method_card", "public_method_card"}


def _containers(finding: Finding | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(finding, Finding):
        return [finding.to_ledger_record(), finding.provenance]
    containers = [finding]
    for key in ("provenance", "metadata"):
        nested = finding.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    return containers


def _first_value(
    finding: Finding | dict[str, Any],
    *keys: str,
) -> Any:
    for container in _containers(finding):
        for key in keys:
            value = container.get(key)
            if value not in (None, ""):
                return value
    return None


def _is_public_method_card(finding: Finding | dict[str, Any]) -> bool:
    source_type = str(_first_value(finding, "source_type") or "").lower()
    category = str(
        _first_value(finding, "finding_category", "type") or ""
    ).lower()
    return source_type == "public_method" or category in _METHOD_CARD_TYPES


def _risk_value(finding: Finding | dict[str, Any]) -> str:
    if isinstance(finding, Finding):
        return finding.risk.value
    raw = finding.get("risk_level", finding.get("risk", RiskLevel.LOW.value))
    if isinstance(raw, RiskLevel):
        return raw.value
    return str(raw).lower()


def _confidence_value(finding: Finding | dict[str, Any]) -> float:
    if isinstance(finding, Finding):
        raw = finding.provenance.get("confidence", 1.0)
    else:
        provenance = finding.get("provenance") or finding.get("metadata") or {}
        raw = provenance.get("confidence", 1.0) if isinstance(provenance, dict) else 1.0
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return min(1.0, max(0.0, confidence))


def _is_open_for_scoring(finding: Finding | dict[str, Any]) -> bool:
    for container in _containers(finding):
        if container.get("open_for_scoring") is False:
            return False
        if container.get("mrpi_eligible") is False:
            return False
        resolution_status = str(container.get("resolution_status") or "").lower()
        if resolution_status in _CLOSED_RESOLUTION_STATUSES:
            return False
    return True


def _evidence_source(finding: Finding | dict[str, Any]) -> str | None:
    source = _first_value(finding, "source_file", "source", "relative_path")
    if source:
        return str(source)
    record = finding.to_ledger_record() if isinstance(finding, Finding) else finding
    evidence = record.get("evidence") or record.get("evidence_items") or []
    if evidence and isinstance(evidence[0], dict):
        value = evidence[0].get("source") or evidence[0].get("relative_path")
        return str(value) if value else None
    return None


def _correlation_key(
    finding: Finding | dict[str, Any],
) -> tuple[str, str, str, str] | None:
    source = _evidence_source(finding)
    table = _first_value(finding, "table_id", "table")
    explicit_group = _first_value(finding, "correlation_group")
    if explicit_group:
        return (
            "explicit",
            "",
            "",
            str(explicit_group),
        )
    method_family = _first_value(finding, "method_family")
    if source and table and method_family:
        return ("method_family", str(source), str(table), str(method_family))
    return None


def calculate_mrpi(findings: Iterable[Finding | dict[str, Any]]) -> float:
    """Calculate Manual Review Priority Index as a 0.0 to 100.0 percentage."""
    total_score = 0.0
    grouped_scores: dict[tuple[str, str, str, str], float] = {}
    for finding in findings:
        if (
            not contributes_to_integrity_mrpi(finding)
            or _is_public_method_card(finding)
            or not _is_open_for_scoring(finding)
        ):
            continue
        weight = RISK_WEIGHTS.get(_risk_value(finding), RISK_WEIGHTS[RiskLevel.LOW.value])
        score = weight * _confidence_value(finding)
        correlation_key = _correlation_key(finding)
        if correlation_key is None:
            total_score += score
        else:
            grouped_scores[correlation_key] = max(
                score,
                grouped_scores.get(correlation_key, 0.0),
            )
    total_score += sum(grouped_scores.values())
    return round(min(1.0, total_score) * 100.0, 2)
