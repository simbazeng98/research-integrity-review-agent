from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from integrity_agent.core.rules.schema import DetectorRule, RuleInputRequirement


class RuleRegistryError(ValueError):
    """Raised when detector rule drafts do not satisfy the runtime contract."""


REQUIRED_RULE_FIELDS = {
    "rule_id",
    "input_required",
    "fields_required",
    "risk_signal",
    "manual_verification",
    "false_positive_risks",
    "safe_report_language",
    "runtime_status",
    "execution_mode",
    "toy_fixture",
    "detector_module",
    "detector_function",
    "requires_network",
    "requires_private_data",
    "risk_ceiling",
}


def _as_list(value: Any, field_name: str, path: Path) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuleRegistryError(f"{path.name}: {field_name} must be a non-empty list")
    return [str(item) for item in value]


def _load_rule(path: Path) -> DetectorRule:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuleRegistryError(f"{path.name}: rule file must contain a mapping")

    missing = sorted(REQUIRED_RULE_FIELDS - set(data))
    if missing:
        raise RuleRegistryError(f"{path.name}: missing required fields: {', '.join(missing)}")

    rule_id = str(data["rule_id"]).strip()
    if not rule_id:
        raise RuleRegistryError(f"{path.name}: rule_id must not be empty")

    safe_language = str(data["safe_report_language"]).strip()
    if not safe_language:
        raise RuleRegistryError(f"{path.name}: safe_report_language must not be empty")

    return DetectorRule(
        rule_id=rule_id,
        status=str(data.get("status", "draft_spec_only")),
        linked_cases=[str(item) for item in data.get("linked_cases", [])],
        input_requirement=RuleInputRequirement(
            input_required=_as_list(data["input_required"], "input_required", path),
            fields_required=_as_list(data["fields_required"], "fields_required", path),
        ),
        risk_signal=str(data["risk_signal"]),
        detection_idea=[str(item) for item in data.get("detection_idea", [])],
        manual_verification=_as_list(
            data["manual_verification"], "manual_verification", path
        ),
        false_positive_risks=_as_list(
            data["false_positive_risks"], "false_positive_risks", path
        ),
        safe_report_language=safe_language,
        runtime_status=str(data["runtime_status"]),
        execution_mode=str(data["execution_mode"]),
        toy_fixture=str(data["toy_fixture"]) if data["toy_fixture"] is not None else None,
        detector_module=str(data["detector_module"]) if data["detector_module"] is not None else None,
        detector_function=str(data["detector_function"]) if data["detector_function"] is not None else None,
        requires_network=bool(data["requires_network"]),
        requires_private_data=bool(data["requires_private_data"]),
        risk_ceiling=str(data["risk_ceiling"]),
        traceability=[str(item) for item in data.get("traceability", [])],
        source_path=path,
        accepted_input_types=[str(item) for item in data.get("accepted_input_types", [])],
        minimum_sample_size=int(data["minimum_sample_size"]) if data.get("minimum_sample_size") is not None else None,
        field_requirements=[str(item) for item in data.get("field_requirements", [])],
        known_false_positive_contexts=[str(item) for item in data.get("known_false_positive_contexts", [])],
    )


def load_rule_registry(rules_dir: Path) -> dict[str, DetectorRule]:
    rules_dir = rules_dir.expanduser().resolve()
    if not rules_dir.exists():
        raise RuleRegistryError(f"Rule directory does not exist: {rules_dir}")

    registry: dict[str, DetectorRule] = {}
    for path in sorted(rules_dir.glob("*.yml")):
        rule = _load_rule(path)
        if rule.rule_id in registry:
            raise RuleRegistryError(f"{path.name}: duplicate rule_id {rule.rule_id}")
        registry[rule.rule_id] = rule

    if not registry:
        raise RuleRegistryError(f"No detector rules found in {rules_dir}")
    return registry
