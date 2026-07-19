"""Human-confirmed atomic claim contracts.

This package intentionally contains deterministic structured-data handling only.
It does not extract claims from PDFs, images, or language-model output.
"""

from integrity_agent.core.claims.schema import (
    AtomicClaim,
    ClaimType,
    DocumentClaim,
    SourceDocument,
    claim_json_schema,
    normalize_claim_value_and_unit,
)

__all__ = [
    "AtomicClaim",
    "ClaimType",
    "DocumentClaim",
    "SourceDocument",
    "claim_json_schema",
    "normalize_claim_value_and_unit",
]
