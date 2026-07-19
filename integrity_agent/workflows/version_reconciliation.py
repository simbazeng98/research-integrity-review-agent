from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from integrity_agent.core.claims.version_schema import (
    CURRENT_PUBLISHER_TYPES,
    PUBLISHER_NOTICE_TYPES,
    ResolutionStatus,
    VersionEvent,
    VersionManifest,
    VersionSourceType,
    load_version_manifest,
    source_precedence,
)
from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.core.safety import find_runtime_safety_issues


class VersionReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    target_doi: str
    resolution_status: ResolutionStatus
    publisher_confirmation: bool
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    counter_evidence: list[dict[str, Any]] = Field(default_factory=list)
    reconciled_findings: list[dict[str, Any]] = Field(default_factory=list)
    open_medium_finding_count: int = 0
    historical_finding_count: int = 0

    def to_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def _coerce_manifest(
    manifest: VersionManifest | Mapping[str, Any] | Path | str,
) -> VersionManifest:
    if isinstance(manifest, VersionManifest):
        return manifest
    if isinstance(manifest, Mapping):
        return VersionManifest.model_validate(dict(manifest))
    return load_version_manifest(manifest)


def _coerce_finding(finding: Any) -> dict[str, Any]:
    if isinstance(finding, Mapping):
        record = deepcopy(dict(finding))
    elif hasattr(finding, "to_ledger_record"):
        record = deepcopy(finding.to_ledger_record())
    elif hasattr(finding, "to_record"):
        record = deepcopy(finding.to_record())
    elif hasattr(finding, "model_dump"):
        record = deepcopy(finding.model_dump(mode="json"))
    else:
        raise TypeError("findings must be mappings or serializable evidence records")
    issues = find_runtime_safety_issues(record)
    if issues:
        raise ValueError(
            "unsafe finding content cannot enter version reconciliation: "
            + "; ".join(sorted(set(issues)))
        )
    return record


def _event_record(event: VersionEvent) -> dict[str, Any]:
    record = event.model_dump(mode="json", exclude_none=True)
    record["status_precedence"] = source_precedence(event.source_type)
    return record


def _chronological_events(events: Iterable[VersionEvent]) -> list[VersionEvent]:
    return sorted(
        events,
        key=lambda event: (
            event.observed_at,
            source_precedence(event.source_type),
            event.event_id,
        ),
    )


def _containers(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    containers: list[Mapping[str, Any]] = [record]
    for key in ("provenance", "metadata"):
        nested = record.get(key)
        if isinstance(nested, Mapping):
            containers.append(nested)
    return containers


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str) and value.strip():
        return {value.strip()}
    if isinstance(value, (list, tuple, set)):
        return {
            str(item).strip()
            for item in value
            if isinstance(item, str) and item.strip()
        }
    return set()


def _finding_links(record: Mapping[str, Any]) -> dict[str, set[str]]:
    finding_ids: set[str] = set()
    event_ids: set[str] = set()
    source_versions: set[str] = set()
    claim_ids: set[str] = set()
    finding_ids |= _string_set(record.get("finding_id"))
    for container in _containers(record):
        event_ids |= _string_set(container.get("version_event_id"))
        event_ids |= _string_set(container.get("version_event_ids"))
        source_versions |= _string_set(container.get("source_version"))
        source_versions |= _string_set(container.get("source_versions"))
        claim_ids |= _string_set(container.get("related_claim_ids"))
        claim_ids |= _string_set(container.get("claim_ids"))
    return {
        "finding_ids": finding_ids,
        "event_ids": event_ids,
        "source_versions": source_versions,
        "claim_ids": claim_ids,
    }


def _observed_events_for_finding(
    events: Sequence[VersionEvent],
    links: Mapping[str, set[str]],
) -> list[VersionEvent]:
    explicit: list[VersionEvent] = []
    inferred: list[VersionEvent] = []
    for event in events:
        if event.event_id in links["event_ids"]:
            explicit.append(event)
            continue
        if links["finding_ids"].intersection(event.related_finding_ids):
            explicit.append(event)
            continue
        version_match = event.source_version in links["source_versions"]
        claim_match = bool(links["claim_ids"].intersection(event.related_claim_ids))
        if version_match and claim_match:
            inferred.append(event)
    return explicit or inferred


def _event_explicitly_applies(
    event: VersionEvent,
    *,
    links: Mapping[str, set[str]],
    observed_events: Sequence[VersionEvent],
) -> bool:
    observed_ids = {item.event_id for item in observed_events}
    observed_versions = {item.source_version for item in observed_events}
    if links["finding_ids"].intersection(event.resolves_finding_ids):
        return True
    if links["finding_ids"].intersection(event.related_finding_ids):
        return True
    if links["claim_ids"].intersection(event.related_claim_ids):
        return True
    if observed_ids.intersection(event.resolves_event_ids):
        return True
    if links["event_ids"].intersection(event.resolves_event_ids):
        return True
    if observed_versions.intersection(event.supersedes_versions):
        return True
    return False


def _resolution_for_finding(
    events: Sequence[VersionEvent],
    record: Mapping[str, Any],
) -> tuple[ResolutionStatus, bool, list[VersionEvent]]:
    links = _finding_links(record)
    observed_events = _observed_events_for_finding(events, links)
    applicable = [
        event
        for event in events
        if event not in observed_events
        and _event_explicitly_applies(
            event,
            links=links,
            observed_events=observed_events,
        )
    ]

    formal = [
        event
        for event in applicable
        if event.source_type in PUBLISHER_NOTICE_TYPES
        and (
            event.resolution_status is ResolutionStatus.FORMALLY_CORRECTED
            or (
                event.source_type
                in {
                    VersionSourceType.PUBLISHER_CORRECTION,
                    VersionSourceType.PUBLISHER_UPDATE,
                }
                and bool(event.resolves_event_ids or event.resolves_finding_ids)
            )
        )
    ]
    if formal:
        return ResolutionStatus.FORMALLY_CORRECTED, True, applicable

    resolved_version = [
        event
        for event in applicable
        if event.source_type in CURRENT_PUBLISHER_TYPES
        and event.resolution_status is ResolutionStatus.RESOLVED_BY_VERSION
    ]
    if resolved_version:
        return ResolutionStatus.RESOLVED_BY_VERSION, True, applicable

    responses = [
        event
        for event in applicable
        if event.source_type
        in {
            VersionSourceType.AUTHOR_RESPONSE,
            VersionSourceType.REVISED_DRAFT,
        }
    ]
    if responses:
        return ResolutionStatus.PARTIALLY_EXPLAINED, False, applicable

    existing = None
    for container in _containers(record):
        raw_status = container.get("resolution_status")
        if raw_status is not None:
            try:
                existing = ResolutionStatus(str(raw_status))
            except ValueError:
                existing = None
            if existing is not None:
                break
    if existing is ResolutionStatus.PARTIALLY_EXPLAINED:
        return existing, False, applicable
    if existing is ResolutionStatus.UNRESOLVED:
        return existing, False, applicable
    return ResolutionStatus.OPEN, False, applicable


def _annotate_finding(
    record: dict[str, Any],
    *,
    status: ResolutionStatus,
    publisher_confirmation: bool,
    timeline: list[dict[str, Any]],
    counter_events: Sequence[VersionEvent],
) -> dict[str, Any]:
    resolved = status in {
        ResolutionStatus.RESOLVED_BY_VERSION,
        ResolutionStatus.FORMALLY_CORRECTED,
    }
    counter_evidence = [
        _event_record(event)
        for event in _chronological_events(counter_events)
        if event.source_type is not VersionSourceType.ORIGINAL_PUBLIC_VERSION
    ]
    existing_tier = None
    source_version = None
    for container in _containers(record):
        if existing_tier is None and container.get("evidence_tier"):
            existing_tier = str(container["evidence_tier"])
        if source_version is None and container.get("source_version"):
            source_version = str(container["source_version"])
    tier_rank = {f"E{index}": index for index in range(5)}
    derived_tier = (
        "E4"
        if status is ResolutionStatus.FORMALLY_CORRECTED
        else "E3" if counter_evidence else "E2"
    )
    evidence_tier = max(
        (existing_tier or "E0", derived_tier),
        key=lambda value: tier_rank.get(value, 0),
    )
    annotation = {
        "evidence_tier": evidence_tier,
        "resolution_status": status.value,
        "publisher_confirmation": publisher_confirmation,
        "open_for_scoring": not resolved,
        "mrpi_eligible": not resolved,
        "historical": resolved,
        "counter_evidence": counter_evidence,
        "version_timeline": deepcopy(timeline),
        "do_not_overclaim": (
            "Publication-version status changes scoring state only; it does not "
            "determine intent or research misconduct."
        ),
    }
    if source_version is not None:
        annotation["source_version"] = source_version
    record.update(annotation)

    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
        record["provenance"] = provenance
    provenance.update(annotation)

    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        metadata.update(annotation)
    return record


def _derive_manifest_status_without_findings(
    events: Sequence[VersionEvent],
) -> tuple[ResolutionStatus, bool]:
    event_ids = {event.event_id for event in events}
    formal = [
        event
        for event in events
        if event.source_type in PUBLISHER_NOTICE_TYPES
        and bool(event_ids.intersection(event.resolves_event_ids))
        and (
            event.resolution_status is ResolutionStatus.FORMALLY_CORRECTED
            or event.source_type
            in {
                VersionSourceType.PUBLISHER_CORRECTION,
                VersionSourceType.PUBLISHER_UPDATE,
            }
        )
    ]
    if formal:
        return ResolutionStatus.FORMALLY_CORRECTED, True
    version_resolved = [
        event
        for event in events
        if event.source_type in CURRENT_PUBLISHER_TYPES
        and event.resolution_status is ResolutionStatus.RESOLVED_BY_VERSION
        and (bool(event_ids.intersection(event.resolves_event_ids)) or event.supersedes_versions)
    ]
    if version_resolved:
        return ResolutionStatus.RESOLVED_BY_VERSION, True
    responses = [
        event
        for event in events
        if event.source_type
        in {VersionSourceType.AUTHOR_RESPONSE, VersionSourceType.REVISED_DRAFT}
        and bool(event_ids.intersection(event.resolves_event_ids))
    ]
    if responses:
        return ResolutionStatus.PARTIALLY_EXPLAINED, False
    return ResolutionStatus.OPEN, False


def _aggregate_status(
    statuses: Sequence[ResolutionStatus],
) -> ResolutionStatus:
    if not statuses:
        return ResolutionStatus.OPEN
    if any(status in {ResolutionStatus.OPEN, ResolutionStatus.UNRESOLVED} for status in statuses):
        if any(status is ResolutionStatus.PARTIALLY_EXPLAINED for status in statuses):
            return ResolutionStatus.PARTIALLY_EXPLAINED
        return ResolutionStatus.OPEN
    if any(status is ResolutionStatus.PARTIALLY_EXPLAINED for status in statuses):
        return ResolutionStatus.PARTIALLY_EXPLAINED
    if any(status is ResolutionStatus.RESOLVED_BY_VERSION for status in statuses):
        return ResolutionStatus.RESOLVED_BY_VERSION
    return ResolutionStatus.FORMALLY_CORRECTED


def reconcile_version_manifest(
    manifest: VersionManifest | Mapping[str, Any] | Path | str,
    *,
    findings: Iterable[Any] = (),
) -> VersionReconciliationResult:
    """Reconcile human-confirmed findings with an offline version manifest.

    Findings are copied, never mutated. A response remains counter-evidence and
    leaves the finding open. Only explicitly linked publisher evidence may make
    an old mismatch historical and ineligible for open MRPI scoring.
    """

    normalized_manifest = _coerce_manifest(manifest)
    events = _chronological_events(normalized_manifest.events)
    timeline = [_event_record(event) for event in events]

    records = [_coerce_finding(finding) for finding in findings]
    reconciled: list[dict[str, Any]] = []
    statuses: list[ResolutionStatus] = []
    confirmations: list[bool] = []
    all_counter_events: list[VersionEvent] = []

    for record in records:
        status, confirmed, counter_events = _resolution_for_finding(events, record)
        statuses.append(status)
        confirmations.append(confirmed)
        for event in counter_events:
            if event not in all_counter_events:
                all_counter_events.append(event)
        reconciled.append(
            _annotate_finding(
                record,
                status=status,
                publisher_confirmation=confirmed,
                timeline=timeline,
                counter_events=counter_events,
            )
        )

    if records:
        overall_status = _aggregate_status(statuses)
        publisher_confirmation = bool(confirmations) and all(confirmations)
    else:
        overall_status, publisher_confirmation = _derive_manifest_status_without_findings(
            events
        )
        all_counter_events = [
            event
            for event in events
            if event.source_type is not VersionSourceType.ORIGINAL_PUBLIC_VERSION
        ]

    open_medium_count = sum(
        1
        for record in reconciled
        if str(record.get("risk_level") or record.get("risk") or "").lower()
        == "medium"
        and record.get("open_for_scoring") is not False
    )
    historical_count = sum(1 for record in reconciled if record.get("historical") is True)

    result = VersionReconciliationResult(
        target_doi=normalized_manifest.target_doi,
        resolution_status=overall_status,
        publisher_confirmation=publisher_confirmation,
        timeline=timeline,
        counter_evidence=[
            _event_record(event)
            for event in _chronological_events(all_counter_events)
        ],
        reconciled_findings=reconciled,
        open_medium_finding_count=open_medium_count,
        historical_finding_count=historical_count,
    )
    issues = find_runtime_safety_issues(result.model_dump(mode="json"))
    if issues:
        raise ValueError(
            "unsafe reconciliation output: " + "; ".join(sorted(set(issues)))
        )
    return result


def reconcile_findings(
    findings: Iterable[Any],
    manifest: VersionManifest | Mapping[str, Any] | Path | str,
) -> list[dict[str, Any]]:
    """Convenience API returning only the copied, reconciled finding records."""

    return reconcile_version_manifest(manifest, findings=findings).reconciled_findings


def run_version_reconciliation(
    manifest_path: Path | str,
    *,
    findings: Iterable[Any] = (),
) -> VersionReconciliationResult:
    """Workflow alias used by the review-package integration layer."""

    return reconcile_version_manifest(manifest_path, findings=findings)


def run_version_reconciliation_detector(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    """Adapter for the repository's existing function-detector contract.

    Version reconciliation annotates existing human-confirmed findings; it does
    not extract claims or create a mismatch from unstructured documents.
    Therefore an invocation without ``options['findings']`` returns no finding.
    """

    options = options or {}
    findings = options.get("findings") or []
    findings = [
        finding
        for finding in findings
        if not (
            isinstance(finding, Mapping)
            and (
                finding.get("human_confirmed") is False
                or (
                    isinstance(finding.get("provenance"), Mapping)
                    and finding["provenance"].get("human_confirmed") is False
                )
            )
        )
    ]
    if not findings:
        return []

    manifest_input = options.get("manifest")
    if manifest_input is None:
        manifest_path = options.get("version_manifest_path")
        if manifest_path is None:
            manifest_path = Path(package_dir) / "documents" / "version_manifest.yml"
        else:
            manifest_path = Path(manifest_path)
            if not manifest_path.is_absolute():
                manifest_path = Path(package_dir) / manifest_path
        if not manifest_path.exists():
            return []
        manifest_input = manifest_path

    result = reconcile_version_manifest(manifest_input, findings=findings)
    rule_records: list[RuleExecutionResult] = []
    for record in result.reconciled_findings:
        evidence_items = record.get("evidence") or record.get("evidence_items") or []
        manual = record.get("manual_verification")
        if not isinstance(manual, dict):
            manual = {
                "needed": True,
                "requests": list(rule.manual_verification),
            }
        metadata = dict(record.get("metadata") or {})
        for key in (
            "source_version",
            "resolution_status",
            "publisher_confirmation",
            "open_for_scoring",
            "mrpi_eligible",
            "historical",
            "counter_evidence",
            "version_timeline",
            "do_not_overclaim",
        ):
            if key in record:
                metadata[key] = record[key]
        provenance = record.get("provenance")
        if isinstance(provenance, dict):
            metadata.setdefault("provenance", provenance)

        risk_level = str(
            record.get("risk_level")
            or record.get("risk")
            or rule.risk_ceiling
        ).lower()
        if risk_level == "high" and rule.risk_ceiling != "high":
            risk_level = rule.risk_ceiling

        rule_records.append(
            RuleExecutionResult(
                finding_id=str(record.get("finding_id") or "publication_version_drift"),
                rule_id=rule.rule_id,
                risk_level=risk_level,
                evidence_items=list(evidence_items),
                manual_verification=manual,
                false_positive_risks=list(
                    record.get("false_positive_risks")
                    or rule.false_positive_risks
                ),
                safe_report_language=str(
                    record.get("safe_report_language")
                    or rule.safe_report_language
                ),
                alternative_explanations=list(
                    record.get("alternative_explanations") or []
                ),
                limitations=list(record.get("limitations") or []),
                metadata=metadata,
            )
        )
    return rule_records


__all__ = [
    "VersionReconciliationResult",
    "reconcile_findings",
    "reconcile_version_manifest",
    "run_version_reconciliation",
    "run_version_reconciliation_detector",
]
