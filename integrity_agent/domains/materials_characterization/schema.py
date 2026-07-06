from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrity_agent.domains.base import SkeletonDomainPlugin


@dataclass
class MaterialsCharMetricRow:
    characterization_method: str | None = None
    instrument_model: str | None = None
    voltage: float | None = None
    pressure: float | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)


class MaterialsCharacterizationDomainPlugin(SkeletonDomainPlugin):
    domain_id = "materials_characterization"
    field_mappings = {
        "characterization_method": [r"xrd", r"xps", r"sem", r"tem", r"method"],
        "instrument_model": [r"instrument", r"model", r"manufacturer"],
        "voltage": [r"voltage", r"\bkv\b", r"accelerating"],
        "pressure": [r"pressure", r"vacuum", r"\bpa\b", r"\btorr\b"],
    }
