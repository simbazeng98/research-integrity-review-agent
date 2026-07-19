"""Deterministic detectors for reviewer-confirmed atomic claims."""

from integrity_agent.detectors.claims.cross_document import (
    CrossDocumentClaimConsistencyDetector,
    compare_cross_document_claims,
    detect_cross_document_claim_consistency,
    run_cross_document_claim_consistency,
)

__all__ = [
    "CrossDocumentClaimConsistencyDetector",
    "compare_cross_document_claims",
    "detect_cross_document_claim_consistency",
    "run_cross_document_claim_consistency",
]
