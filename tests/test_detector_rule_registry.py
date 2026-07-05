from pathlib import Path

import pytest

from integrity_agent.core.rules.registry import RuleRegistryError, load_rule_registry


def test_detector_rule_registry_loads_all_draft_rules():
    project_root = Path(__file__).resolve().parents[1]
    registry = load_rule_registry(project_root / "knowledge_base" / "detector_rules")

    assert len(registry) >= 11
    assert "numeric_fixed_delta_between_columns" in registry
    assert "numeric_terminal_digit_anomaly" in registry
    assert "retraction_metadata_check" in registry
    assert "image_exact_duplicate_sha256" in registry
    assert "image_perceptual_similarity_candidate" in registry
    assert registry["numeric_fixed_delta_between_columns"].safe_report_language
    assert registry["numeric_fixed_delta_between_columns"].input_requirement.input_required


def test_detector_rule_registry_rejects_missing_rule_id(tmp_path):
    bad_rule = tmp_path / "bad_rule.yml"
    bad_rule.write_text(
        "\n".join(
            [
                "status: draft_spec_only",
                "input_required:",
                "  - source_table",
                "fields_required:",
                "  - numeric_matrix",
                "risk_signal: missing rule id",
                "manual_verification:",
                "  - raw data",
                "false_positive_risks:",
                "  - rounded values",
                "safe_report_language: Candidate risk signal.",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuleRegistryError, match="rule_id"):
        load_rule_registry(tmp_path)


def test_detector_rule_registry_rejects_missing_safe_report_language(tmp_path):
    bad_rule = tmp_path / "bad_rule.yml"
    bad_rule.write_text(
        "\n".join(
            [
                "rule_id: missing_safe_language",
                "status: draft_spec_only",
                "input_required:",
                "  - source_table",
                "fields_required:",
                "  - numeric_matrix",
                "risk_signal: missing safe language",
                "manual_verification:",
                "  - raw data",
                "false_positive_risks:",
                "  - rounded values",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuleRegistryError, match="safe_report_language"):
        load_rule_registry(tmp_path)


@pytest.mark.parametrize(
    "missing_field",
    [
        "runtime_status",
        "execution_mode",
        "toy_fixture",
        "detector_module",
        "detector_function",
        "requires_network",
        "requires_private_data",
        "risk_ceiling",
    ],
)
def test_detector_rule_registry_rejects_missing_new_fields(tmp_path, missing_field):
    fields = {
        "rule_id": "test_rule",
        "status": "draft_spec_only",
        "input_required": ["source_table"],
        "fields_required": ["numeric_matrix"],
        "risk_signal": "test signal",
        "manual_verification": ["raw data"],
        "false_positive_risks": ["rounded values"],
        "safe_report_language": "Candidate test signal",
        "runtime_status": "draft_spec_only",
        "execution_mode": "offline",
        "toy_fixture": None,
        "detector_module": None,
        "detector_function": None,
        "requires_network": False,
        "requires_private_data": False,
        "risk_ceiling": "medium",
    }
    del fields[missing_field]

    bad_rule = tmp_path / "bad_rule.yml"
    import yaml
    bad_rule.write_text(yaml.safe_dump(fields), encoding="utf-8")

    with pytest.raises(RuleRegistryError, match=missing_field):
        load_rule_registry(tmp_path)

