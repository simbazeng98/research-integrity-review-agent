from __future__ import annotations

from pathlib import Path
from integrity_agent.core.rules.registry import load_rule_registry


def test_image_similarity_rule_loads():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")
    
    assert "image_perceptual_similarity_candidate" in registry
    rule = registry["image_perceptual_similarity_candidate"]
    
    assert rule.rule_id == "image_perceptual_similarity_candidate"
    assert rule.runtime_status == "active"
    assert rule.execution_mode == "offline"
    assert rule.requires_network is False
    assert rule.risk_ceiling == "medium"
    assert "Candidate visual similarity" in rule.safe_report_language
    assert "small/simple synthetic images" in rule.false_positive_risks
    assert "original unprocessed image files" in rule.manual_verification
