import json
import subprocess
import sys
from pathlib import Path


def test_run_rules_cli_generates_traceable_rule_findings():
    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "outputs" / "rule_findings.jsonl"
    if output_path.exists():
        output_path.unlink()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "run-rules",
            "examples/toy_rule_package",
        ],
        check=False,
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rule_ids = {record["rule_id"] for record in records}
    assert {
        "numeric_fixed_delta_between_columns",
        "numeric_terminal_digit_anomaly",
        "retraction_metadata_check",
    }.issubset(rule_ids)

    for record in records:
        assert record["finding_id"]
        assert record["risk_level"] in {"low", "medium", "high"}
        assert record["evidence_items"]
        assert record["manual_verification"]["needed"] is True
        assert record["false_positive_risks"]
        assert "candidate" in record["safe_report_language"].lower() or "signal" in record[
            "safe_report_language"
        ].lower()


def test_run_rules_cli_allow_network(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "findings.jsonl"
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "run-rules",
            "examples/toy_rule_package",
            "--output",
            str(output_path),
            "--allow-network",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    
    records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    meta_records = [r for r in records if r["rule_id"] == "retraction_metadata_check"]
    assert len(meta_records) == 1
    assert meta_records[0]["evidence_items"][0]["status"] == "expression_of_concern"


def test_crossref_detector_offline_versus_online():
    from integrity_agent.detectors.metadata.crossref_retraction_check import CrossrefRetractionDetector
    from integrity_agent.core.rules.schema import DetectorRule, RuleInputRequirement
    import tempfile
    import yaml
    
    rule = DetectorRule(
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
    
    detector = CrossrefRetractionDetector()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mock_file = tmpdir_path / "toy_metadata_mock.yml"
        mock_file.write_text(yaml.safe_dump({
            "identifier": "10.0000/toy-retracted",
            "mock_public_status": "retraction",
            "notice_url": "http://example.invalid"
        }), encoding="utf-8")
        
        # Test offline mode with retraction status
        findings = detector.detect(tmpdir_path, rule, options={"allow_network": False})
        assert len(findings) == 1
        assert findings[0].risk_level == "high"
        assert findings[0].evidence_items[0]["status"] == "retraction"
        
        # Test online mode with a nonexistent DOI which will fallback to metadata_unavailable
        mock_file.write_text(yaml.safe_dump({
            "identifier": "10.0000/toy-non-existent",
            "mock_public_status": "none"
        }), encoding="utf-8")
        findings_online = detector.detect(tmpdir_path, rule, options={"allow_network": True})
        assert len(findings_online) == 1
        assert findings_online[0].evidence_items[0]["status"] == "metadata_unavailable"


