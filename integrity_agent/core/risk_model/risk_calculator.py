from __future__ import annotations

from typing import Any, Iterable

from integrity_agent.core.evidence.schema import Finding, RiskLevel


RISK_WEIGHTS = {
    RiskLevel.HIGH.value: 0.35,
    RiskLevel.MEDIUM.value: 0.15,
    RiskLevel.LOW.value: 0.05,
}


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


def calculate_mrpi(findings: Iterable[Finding | dict[str, Any]]) -> float:
    """Calculate Manual Review Priority Index as a 0.0 to 100.0 percentage."""
    total_score = 0.0
    for finding in findings:
        weight = RISK_WEIGHTS.get(_risk_value(finding), RISK_WEIGHTS[RiskLevel.LOW.value])
        total_score += weight * _confidence_value(finding)
    return round(min(1.0, total_score) * 100.0, 2)
