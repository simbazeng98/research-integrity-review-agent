from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.domains.base import SkeletonDomainPlugin


@dataclass
class AIMLBenchmarkRow:
    model_name: str | None = None
    dataset_name: str | None = None
    metric: str | None = None
    reported_score: float | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)


class AIMLDomainPlugin(SkeletonDomainPlugin):
    domain_id = "ai_ml"
    field_mappings = {
        "model_name": [r"model", r"architecture"],
        "dataset_name": [r"dataset", r"benchmark", r"corpus"],
        "metric": [r"metric", r"accuracy", r"f1", r"auc"],
        "reported_score": [r"score", r"reported", r"performance"],
    }
