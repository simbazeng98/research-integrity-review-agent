from __future__ import annotations

from pathlib import Path
from integrity_agent.core.rules.registry import load_rule_registry


def test_image_exact_duplicate_rule_loads():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    
    assert "image_exact_duplicate_sha256" in registry
    rule = registry["image_exact_duplicate_sha256"]
    
    assert rule.rule_id == "image_exact_duplicate_sha256"
    assert rule.runtime_status == "active"
    assert rule.execution_mode == "offline"
    assert rule.requires_network is False
    assert rule.risk_ceiling == "medium"
    assert "Exact duplicate image" in rule.safe_report_language
    assert "repeated control image" in rule.false_positive_risks
    assert "original image files" in rule.manual_verification
