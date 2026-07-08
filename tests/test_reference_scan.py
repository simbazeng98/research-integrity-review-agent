from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from integrity_agent.workflows.reference_scan import run_reference_scan
from integrity_agent.workflows.validate_ledger import validate_ledger_file


def test_reference_scan_anomalies_workflow(tmp_path):
    # Create test input TXT file
    input_txt = tmp_path / "test_references.txt"
    references_lines = [
        "1. Smith et al., Journal of Science, 2020. doi: 10.1002/adma.202000000",
        "2. Duplicate entry of the same DOI: https://doi.org/10.1002/adma.202000000",
        "3. Malformed DOI entry: doi: 10.99/invalid/doi/prefix/here",
        "4. Very short ref",  # Incomplete & missing DOI
        "5. Article with mock retraction: doi: 10.0000/toy-retracted",
        "6. Article with mock correction: doi: 10.0000/toy-corrected",
        "7. Article with mock concern: doi: 10.0000/toy-eoc",
        "8. Normal article without DOI",  # Missing DOI but has year (2021) and title
    ]
    input_txt.write_text("\n".join(references_lines), encoding="utf-8")

    output_dir = tmp_path / "outputs"

    # Run the scan workflow
    jsonl_path, summary_path = run_reference_scan(
        input_path=input_txt,
        allow_network=False,
        output_dir=output_dir,
    )

    assert jsonl_path.exists()
    assert summary_path.exists()

    # Load findings
    findings = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # 1. Validate schema and privacy using validate-ledger
    validation_result = validate_ledger_file(jsonl_path)
    assert validation_result.ok is True
    assert validation_result.records > 0

    # 2. Check for duplicate DOI
    dup_findings = [f for f in findings if f.get("rule_id") == "duplicate_reference"]
    assert len(dup_findings) >= 1
    assert any("10.1002/adma.202000000" in f["provenance"].get("duplicate_item", "") for f in dup_findings)

    # 3. Check for malformed DOI
    malformed_findings = [f for f in findings if f.get("rule_id") == "malformed_doi"]
    assert len(malformed_findings) >= 1
    assert any("10.99/invalid/doi/prefix/here" in f["provenance"].get("raw_doi", "") for f in malformed_findings)

    # 4. Check for missing DOI
    missing_findings = [f for f in findings if f.get("rule_id") == "missing_doi"]
    assert len(missing_findings) >= 1

    # 5. Check for incomplete reference
    incomplete_findings = [f for f in findings if f.get("rule_id") == "incomplete_reference_metadata"]
    assert len(incomplete_findings) >= 1
    # "Very short ref" should trigger incomplete reference metadata
    assert any("Very short ref" in f["evidence"][0]["quote"] for f in incomplete_findings)

    # 6. Check for retracted mock DOI
    retracted_findings = [f for f in findings if f.get("rule_id") == "retracted_reference"]
    assert len(retracted_findings) == 1
    assert retracted_findings[0]["provenance"]["doi"] == "10.0000/toy-retracted"
    assert retracted_findings[0]["risk"] == "high"

    # 7. Check for corrected mock DOI
    corrected_findings = [f for f in findings if f.get("rule_id") == "corrected_reference"]
    assert len(corrected_findings) == 3
    assert any(f["provenance"]["doi"] == "10.0000/toy-corrected" for f in corrected_findings)
    assert corrected_findings[0]["risk"] == "low"

    # 8. Check for EOC mock DOI
    concern_findings = [f for f in findings if f.get("rule_id") == "expression_of_concern_reference"]
    assert len(concern_findings) == 1
    assert concern_findings[0]["provenance"]["doi"] == "10.0000/toy-eoc"
    assert concern_findings[0]["risk"] == "medium"

    # 9. Verify safety language does not contain fraud/fake/verdict-like phrases
    summary_content = summary_path.read_text(encoding="utf-8")
    assert "not proof of research misconduct" in summary_content

    for f in findings:
        for val in [f.get("summary"), f.get("safe_report_language")]:
            if not val:
                continue
            text = str(val)
            assert "fraud" not in text.lower()
            assert "fake" not in text.lower()
            assert "misconduct proven" not in text.lower()


def test_reference_scan_jsonl_input(tmp_path):
    input_jsonl = tmp_path / "references.jsonl"
    records = [
        {"text": "Smith 2020", "doi": "10.1002/adma.202000000"},
        {"text": "Jones 2021", "doi": "10.1002/adma.202000000"}, # Duplicate DOI
        {"text": "Short", "doi": ""}, # Incomplete / missing DOI
    ]
    with open(input_jsonl, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    output_dir = tmp_path / "outputs"
    jsonl_path, _ = run_reference_scan(input_jsonl, output_dir=output_dir)

    findings = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    assert any(f.get("rule_id") == "duplicate_reference" for f in findings)
    assert any(f.get("rule_id") == "incomplete_reference_metadata" for f in findings)


def test_reference_scan_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    input_txt = tmp_path / "references.txt"
    input_txt.write_text("1. doi:10.1002/adma.202000000\n2. doi:10.1002/adma.202000000\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "reference-scan",
            str(input_txt),
            "-o",
            str(output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "reference_anomalies.jsonl").exists()
    assert (output_dir / "reference_anomaly_summary.md").exists()
