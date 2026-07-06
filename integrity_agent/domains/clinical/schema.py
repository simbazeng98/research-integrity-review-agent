from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.domains.base import SkeletonDomainPlugin


@dataclass
class ClinicalTrialMetricRow:
    trial_id: str | None = None
    arm_name: str | None = None
    group_size: int | None = None
    age_mean: float | None = None
    age_sd: float | None = None
    p_val: float | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)


class ClinicalDomainPlugin(SkeletonDomainPlugin):
    domain_id = "clinical"
    field_mappings = {
        "trial_id": [r"\btrial[_ -]?id\b", r"\bnct\b", r"registration"],
        "arm_name": [r"\barm\b", r"group", r"treatment"],
        "group_size": [r"\bn\b", r"sample[_ -]?size", r"group[_ -]?size"],
        "age_mean": [r"age.*mean", r"mean.*age"],
        "age_sd": [r"age.*sd", r"age.*standard deviation"],
        "p_val": [r"\bp[_ -]?val", r"\bp value\b"],
    }
