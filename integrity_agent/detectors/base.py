from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult


class BaseDetector(ABC):
    """Base class for all research integrity detectors."""

    runtime_status: str = "draft_spec_only"
    execution_mode: str = "offline"
    risk_ceiling: str = "medium"
    requires_network: bool = False
    requires_private_data: bool = False

    @abstractmethod
    def detect(
        self,
        package_dir: Path,
        rule: DetectorRule,
        options: dict[str, Any] | None = None,
    ) -> list[RuleExecutionResult]:
        """Run detection logic against the package directory for a given rule.

        Args:
            package_dir: Path to the rule package directory containing target files.
            rule: The DetectorRule instance containing metadata and configuration.
            options: Optional runtime parameters (e.g. allow_network).

        Returns:
            A list of RuleExecutionResult findings.
        """
        pass
