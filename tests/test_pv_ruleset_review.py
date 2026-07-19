from __future__ import annotations

import json
import subprocess
import sys

from integrity_agent.workflows.pv_ruleset_review import run_pv_ruleset_review
from integrity_agent.workflows.validate_ledger import validate_ledger_file
from integrity_agent.core.safety import FORBIDDEN_VERDICT_PHRASES

def test_pv_ruleset_review_workflow(tmp_path):
    # 1. Create a toy PV table CSV file that is missing mask_area, scan_direction, stability metadata, and EQE Jsc
    csv_file = tmp_path / "toy_pv.csv"
    csv_content = (
        "Device ID,Voc (V),Jsc (mA/cm2),FF (%),PCE (%)\n"
        "device-1,1.10,22.0,75.0,18.15\n"
        "device-2,1.11,21.8,76.0,18.41\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    # Create a manifest for table intake
    manifest_jsonl = tmp_path / "table_manifest.jsonl"
    manifest_item = {
        "table_id": "tbl-1",
        "source_file": "toy_pv.csv",
        "relative_path": str(csv_file),
        "source_format": "csv",
        "sheet_name": None,
        "row_count": 2,
        "column_count": 5,
        "columns": ["Device ID", "Voc (V)", "Jsc (mA/cm2)", "FF (%)", "PCE (%)"],
        "warnings": []
    }
    with manifest_jsonl.open("w", encoding="utf-8") as f:
        f.write(json.dumps(manifest_item) + "\n")

    # 2. Run the pv ruleset review workflow on the manifest
    output_dir = tmp_path / "outputs"
    findings_file, summary_file, _ = run_pv_ruleset_review(
        input_path=manifest_jsonl,
        output_dir=output_dir
    )

    assert findings_file.exists()
    assert summary_file.exists()

    # Load findings
    findings = []
    with findings_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    assert len(findings) > 0

    # Ensure finding_category is pv_evidence_completeness
    for f in findings:
        assert f["finding_category"] == "pv_evidence_completeness"
        assert f["needs_manual_review"] is True
        assert f["manual_verification"]["needed"] is True

        # Assert no forbidden phrases
        safe_lang = f["safe_report_language"].lower()
        for forbidden in FORBIDDEN_VERDICT_PHRASES:
            assert forbidden.lower() not in safe_lang, f"Finding contains forbidden phrase: {forbidden}"

    # Verify that missing mask_area, scan_direction, etc., generated low-risk completeness findings
    mask_area_finding = next((f for f in findings if f["rule_id"] == "pv_jv_mask_area_completeness"), None)
    assert mask_area_finding is not None
    assert mask_area_finding["risk"] == "low"
    assert "mask area" in mask_area_finding["safe_report_language"].lower()

    scan_dir_finding = next((f for f in findings if f["rule_id"] == "pv_jv_scan_direction_completeness"), None)
    assert scan_dir_finding is not None
    assert scan_dir_finding["risk"] == "low"
    assert "scan direction" in scan_dir_finding["safe_report_language"].lower()

    # Verify high ceiling rule raw/source-data caveat
    eqe_finding = next((f for f in findings if f["rule_id"] == "pv_eqe_integrated_jsc_consistency"), None)
    assert eqe_finding is not None
    assert eqe_finding["risk"] == "high"
    assert "raw/source-data" in eqe_finding["safe_report_language"].lower()

    # 3. Validate ledger schema using validate_ledger_file
    validation_res = validate_ledger_file(findings_file)
    assert len(validation_res.issues) == 0, f"Ledger validation failed: {validation_res.issues}"

    # Check for absolute paths
    for path in [findings_file, summary_file]:
        text = path.read_text(encoding="utf-8").lower()
        for pattern in ["file:///", "d:/", "c:/", "d:\\", "c:\\"]:
            assert pattern not in text, f"Forbidden pattern '{pattern}' leaked into {path.name}"


def test_pv_ruleset_review_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "pv-ruleset-review", "--help"],
        text=True,
        capture_output=True,
        check=True
    )
    assert "pv-ruleset-review" in result.stdout
    assert "--column-profiles" in result.stdout


def test_pv_ruleset_review_cli_run(tmp_path):
    # Test running CLI on a directory containing table files
    csv_file = tmp_path / "toy_pv.csv"
    csv_content = (
        "Device ID,Voc (V),Jsc (mA/cm2),FF (%),PCE (%)\n"
        "device-1,1.10,22.0,75.0,18.15\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    output_dir = tmp_path / "outputs"
    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "pv-ruleset-review", str(tmp_path), "-o", str(output_dir)],
        text=True,
        capture_output=True,
        check=True
    )

    assert result.returncode == 0
    assert "pv_ruleset_findings.jsonl" in result.stdout
    assert "pv_ruleset_review_summary.md" in result.stdout

    findings_file = output_dir / "pv_ruleset_findings.jsonl"
    summary_file = output_dir / "pv_ruleset_review_summary.md"
    assert findings_file.exists()
    assert summary_file.exists()

    # Load findings
    findings = []
    with findings_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # Assert findings > 0
    assert len(findings) > 0

    # Assert specific rule_ids are present
    rule_ids = {f["rule_id"] for f in findings}
    assert "pv_jv_mask_area_completeness" in rule_ids
    assert "pv_jv_scan_direction_completeness" in rule_ids

    # Assert validate-ledger passes
    validation_res = validate_ledger_file(findings_file)
    assert len(validation_res.issues) == 0, f"Ledger validation failed: {validation_res.issues}"

    # Assert no absolute paths in findings or summary
    for path in [findings_file, summary_file]:
        text = path.read_text(encoding="utf-8")
        text_lower = text.lower()
        for pattern in ["file:///", "d:/", "c:/", "d:\\", "c:\\"]:
            assert pattern not in text_lower, f"Forbidden absolute path pattern '{pattern}' found in {path.name}"
