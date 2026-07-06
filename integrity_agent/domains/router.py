from __future__ import annotations

from integrity_agent.domains.ai_ml.schema import AIMLDomainPlugin
from integrity_agent.domains.base import BaseDomainPlugin, DomainColumnMatch
from integrity_agent.domains.biomedical.schema import BiomedicalDomainPlugin
from integrity_agent.domains.chemistry.schema import ChemistryDomainPlugin
from integrity_agent.domains.clinical.schema import ClinicalDomainPlugin
from integrity_agent.domains.materials_characterization.schema import (
    MaterialsCharacterizationDomainPlugin,
)
from integrity_agent.domains.psychology_social_science.schema import (
    PsychologySocialScienceDomainPlugin,
)


def available_domain_plugins() -> list[BaseDomainPlugin]:
    return [
        ClinicalDomainPlugin(),
        BiomedicalDomainPlugin(),
        ChemistryDomainPlugin(),
        MaterialsCharacterizationDomainPlugin(),
        AIMLDomainPlugin(),
        PsychologySocialScienceDomainPlugin(),
    ]


def route_table_columns(
    columns: list[str],
    plugins: list[BaseDomainPlugin] | None = None,
    min_score: float = 0.0,
) -> list[DomainColumnMatch]:
    candidates = plugins if plugins is not None else available_domain_plugins()
    matches = [plugin.match_columns(columns) for plugin in candidates]
    filtered = [match for match in matches if match.score >= min_score]
    return sorted(filtered, key=lambda match: (-match.score, match.domain_id))
