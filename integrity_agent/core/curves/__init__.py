"""Structured contracts for supplied source-data and plot-data tables."""

from integrity_agent.core.curves.schema import (
    CurveColumnMapping,
    CurveDisclosure,
    CurveInterval,
    CurvePoint,
    CurveReconciliationSpec,
    CurveSegmentSimilarityOptions,
    CurveTableSpec,
    curve_reconciliation_json_schema,
)

__all__ = [
    "CurveColumnMapping",
    "CurveDisclosure",
    "CurveInterval",
    "CurvePoint",
    "CurveReconciliationSpec",
    "CurveSegmentSimilarityOptions",
    "CurveTableSpec",
    "curve_reconciliation_json_schema",
]
