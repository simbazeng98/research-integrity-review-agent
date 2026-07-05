from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from integrity_agent.core.rules.registry import load_rule_registry
from integrity_agent.core.rules.schema import RuleExecutionResult
from integrity_agent.detectors.registry import run_detector

DEFAULT_OUTPUT = Path("outputs") / "rule_findings.jsonl"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_rules(
    package_dir: Path,
    output_path: Path = DEFAULT_OUTPUT,
    allow_network: bool = False,
) -> Path:
    package_dir = package_dir.expanduser()
    if not package_dir.is_absolute():
        package_dir = Path.cwd() / package_dir
    package_dir = package_dir.resolve()

    # Load rules from registry
    registry = load_rule_registry(_project_root() / "knowledge_base" / "detector_rules")
    findings: list[RuleExecutionResult] = []

    # Active rules mapped to detectors
    active_rules = [
        "numeric_fixed_delta_between_columns",
        "numeric_terminal_digit_anomaly",
        "retraction_metadata_check",
    ]

    options = {"allow_network": allow_network}

    for rule_id in active_rules:
        rule = registry.get(rule_id)
        if rule:
            findings.extend(run_detector(rule, package_dir, options=options))

    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(finding.to_json_line() + "\n" for finding in findings),
        encoding="utf-8",
    )
    return output_path.resolve()


def iter_rule_findings(path: Path) -> Iterable[dict[str, Any]]:
    import json

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)
