from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.domains.base import SkeletonDomainPlugin


@dataclass
class PsychologyMetricRow:
    mean: float | None = None
    std_dev: float | None = None
    t_value: float | None = None
    f_value: float | None = None
    df: float | None = None
    sample_size: int | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)


class PsychologySocialScienceDomainPlugin(SkeletonDomainPlugin):
    domain_id = "psychology_social_science"
    field_mappings = {
        "mean": [r"\bmean\b", r"\bm\b"],
        "std_dev": [r"std", r"standard deviation", r"\bsd\b"],
        "t_value": [r"\bt\b", r"t[_ -]?value"],
        "f_value": [r"\bf\b", r"f[_ -]?value"],
        "df": [r"\bdf\b", r"degrees of freedom"],
        "sample_size": [r"\bn\b", r"sample[_ -]?size"],
    }
