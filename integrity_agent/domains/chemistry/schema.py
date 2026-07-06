from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.domains.base import SkeletonDomainPlugin


@dataclass
class ChemistrySpectrumMetricRow:
    peak_shift: float | None = None
    multiplicity: str | None = None
    coupling_constant: float | None = None
    element_percentage: float | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)


class ChemistryDomainPlugin(SkeletonDomainPlugin):
    domain_id = "chemistry"
    field_mappings = {
        "peak_shift": [r"peak", r"shift", r"chemical shift", r"\bppm\b"],
        "multiplicity": [r"multiplicity", r"\bsinglet\b", r"\bdoublet\b"],
        "coupling_constant": [r"coupling", r"\bj\b.*hz", r"constant"],
        "element_percentage": [r"element", r"percent", r"analysis"],
    }
