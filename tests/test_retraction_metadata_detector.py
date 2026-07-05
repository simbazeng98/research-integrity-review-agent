from __future__ import annotations

from pathlib import Path
import tempfile
import yaml
import pytest

from integrity_agent.core.rules.schema import DetectorRule, RuleInputRequirement
from integrity_agent.detectors.metadata.crossref_retraction_check import CrossrefRetractionDetector


@pytest.fixture
def base_rule():
    return DetectorRule(
        rule_id="retraction_metadata_check",
        input_requirement=RuleInputRequirement(input_required=["doi"], fields_required=["identifier"]),
        risk_signal="test",
        manual_verification=["check"],
        false_positive_risks=["none"],
        safe_report_language="safe language",
        runtime_status="active",
        execution_mode="hybrid",
        toy_fixture="toy_metadata_mock.yml",
        detector_module="integrity_agent.detectors.metadata.crossref_retraction_check",
        detector_function="check_retraction_metadata",
        requires_network=True,
        requires_private_data=False,
        risk_ceiling="medium",
    )


def test_crossref_detector_no_metadata_file(base_rule):
    detector = CrossrefRetractionDetector()
    with tempfile.TemporaryDirectory() as tmpdir:
        # No file exists
        findings = detector.detect(Path(tmpdir), base_rule)
        assert findings == []


def test_crossref_detector_no_known_update_omitted(base_rule):
    detector = CrossrefRetractionDetector()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mock_file = tmpdir_path / "toy_metadata_mock.yml"
        mock_file.write_text(
            yaml.safe_dump({"identifier": "10.0000/toy-no-update", "mock_public_status": "no_known_update"}),
            encoding="utf-8"
        )
        
        findings = detector.detect(tmpdir_path, base_rule, options={"allow_network": False})
        # no_known_update does not produce findings
        assert findings == []


def test_crossref_detector_retraction_high_risk(base_rule):
    detector = CrossrefRetractionDetector()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mock_file = tmpdir_path / "toy_metadata_mock.yml"
        mock_file.write_text(
            yaml.safe_dump({"identifier": "10.0000/toy-retracted", "mock_public_status": "retraction"}),
            encoding="utf-8"
        )
        
        findings = detector.detect(tmpdir_path, base_rule, options={"allow_network": False})
        assert len(findings) == 1
        f = findings[0]
        assert f.risk_level == "high"
        assert f.metadata["crossref_update_status"] == "retraction"
        assert f.metadata["detector_id"] == "crossref_retraction_check"
        assert f.metadata["source_strength"] == "toy_or_synthetic"
