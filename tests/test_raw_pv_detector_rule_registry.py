from __future__ import annotations

from pathlib import Path
from integrity_agent.core.rules.registry import load_rule_registry

def test_raw_pv_detector_rule_registry_loads_new_rules():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")

    new_rules = [
        "pv_jv_metric_recalculation",
        "pv_jv_hysteresis_candidate",
        "pv_eqe_spectrum_integration",
        "pv_excel_formula_audit",
        "pv_source_reconciliation"
    ]

    for rule_id in new_rules:
        assert rule_id in registry, f"Rule '{rule_id}' was not loaded by the registry."
        rule = registry[rule_id]
        assert rule.risk_ceiling == "medium", f"Rule '{rule_id}' must have a risk ceiling of 'medium'."
        assert rule.requires_network is False, f"Rule '{rule_id}' must run offline."
