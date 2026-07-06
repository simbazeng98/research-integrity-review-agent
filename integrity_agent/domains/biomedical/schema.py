from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.domains.base import SkeletonDomainPlugin


@dataclass
class BiomedicalMetricRow:
    gene_symbol: str | None = None
    expression_level: float | None = None
    band_intensity: float | None = None
    p_val: float | None = None
    sample_id: str | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)


class BiomedicalDomainPlugin(SkeletonDomainPlugin):
    domain_id = "biomedical"
    field_mappings = {
        "gene_symbol": [r"gene", r"symbol", r"target"],
        "expression_level": [r"expression", r"fold[_ -]?change", r"qpcr"],
        "band_intensity": [r"band.*intensity", r"western", r"blot"],
        "p_val": [r"\bp[_ -]?val", r"\bp value\b"],
        "sample_id": [r"sample[_ -]?id", r"specimen"],
    }
