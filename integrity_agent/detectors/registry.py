from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.detectors.base import BaseDetector

_DETECTORS: dict[str, Any] = {}


class DetectorRegistryError(ValueError):
    """Raised when a detector cannot be loaded or is invalid."""
    pass


def register_detector(rule_id: str, detector: Any) -> None:
    """Register a detector for a given rule_id."""
    _DETECTORS[rule_id] = detector


def get_detector(rule: DetectorRule) -> Any:
    """Retrieve the detector for a rule, loading dynamically if needed."""
    if rule.rule_id in _DETECTORS:
        return _DETECTORS[rule.rule_id]

    if not rule.detector_module or not rule.detector_function:
        raise DetectorRegistryError(
            f"Rule '{rule.rule_id}' does not specify detector_module or detector_function."
        )

    try:
        mod = importlib.import_module(rule.detector_module)
    except ImportError as e:
        raise DetectorRegistryError(
            f"Failed to import detector module '{rule.detector_module}' for rule '{rule.rule_id}': {e}"
        )

    try:
        func = getattr(mod, rule.detector_function)
    except AttributeError:
        raise DetectorRegistryError(
            f"Module '{rule.detector_module}' has no function '{rule.detector_function}' for rule '{rule.rule_id}'."
        )

    # Register/Cache it
    register_detector(rule.rule_id, func)
    return func


def run_detector(
    rule: DetectorRule,
    package_dir: Path,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    """Execute the detector associated with the rule."""
    detector = get_detector(rule)
    if isinstance(detector, type) and issubclass(detector, BaseDetector):
        instance = detector()
        return instance.detect(package_dir, rule, options)
    elif callable(detector):
        # Functions can be called directly
        return detector(package_dir, rule, options)
    else:
        raise DetectorRegistryError(f"Detector for rule '{rule.rule_id}' is not callable.")


def list_loaded_detectors() -> list[str]:
    """Return list of rule IDs with loaded detectors."""
    return sorted(_DETECTORS.keys())
