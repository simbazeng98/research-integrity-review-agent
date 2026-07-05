from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.detectors.base import BaseDetector


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


class MockRetractionDetector(BaseDetector):
    runtime_status = "active"
    execution_mode = "offline"
    risk_ceiling = "medium"
    requires_network = False
    requires_private_data = False

    def detect(
        self,
        package_dir: Path,
        rule: DetectorRule,
        options: dict[str, Any] | None = None,
    ) -> list[RuleExecutionResult]:
        metadata_path = package_dir / "toy_metadata_mock.yml"
        if not metadata_path.exists():
            return []
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        status = str(metadata.get("mock_public_status", "none"))
        if status == "none":
            return []

        return [
            RuleExecutionResult(
                finding_id="RR-003",
                rule_id=rule.rule_id,
                risk_level="low",
                evidence_items=[
                    {
                        "source": (
                            metadata_path.relative_to(_project_root()).as_posix()
                            if metadata_path.is_relative_to(_project_root())
                            else metadata_path.as_posix()
                        ),
                        "location": "mock_public_status",
                        "observed_pattern": f"mock status is {status}",
                        "identifier": metadata.get("identifier"),
                    }
                ],
                manual_verification={"needed": True, "requests": list(rule.manual_verification)},
                false_positive_risks=rule.false_positive_risks,
                safe_report_language=rule.safe_report_language,
                alternative_explanations=[
                    "Metadata may describe a correction, withdrawal, or context notice rather than article-level misconduct.",
                    "Mock metadata is synthetic and may not correspond to a real DOI.",
                ],
                missing_verification_materials=rule.manual_verification,
                suggested_verification_questions=[
                    "Please verify the notice text from the publisher or authoritative metadata source.",
                    "Please distinguish retraction, correction, withdrawal, and expression of concern.",
                ],
                limitations=[
                    "This MVP uses mock metadata only and performs no network lookup.",
                ],
                metadata={
                    "detector_mode": "mock_metadata",
                    "mock_public_status": status,
                    "runtime_status": self.runtime_status,
                    "execution_mode": self.execution_mode,
                    "risk_ceiling": self.risk_ceiling,
                    "requires_network": self.requires_network,
                    "requires_private_data": self.requires_private_data,
                },
            )
        ]


def check_mock_metadata(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return MockRetractionDetector().detect(package_dir, rule, options)
