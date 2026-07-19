from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.validate_ledger import validate_ledger_file


def test_review_package_reference_scan_integration(tmp_path):
    project_root = Path(__file__).resolve().parents[1]

    # 1. Create a copy of the toy review package
    toy_pkg_src = project_root / "examples/toy_review_package"
    pkg_with_ref = tmp_path / "toy_review_package_with_ref"
    pkg_with_ref.mkdir()

    # Copy standard subdirectories
    shutil.copytree(toy_pkg_src / "images", pkg_with_ref / "images")
    shutil.copytree(toy_pkg_src / "tables", pkg_with_ref / "tables")
    shutil.copytree(toy_pkg_src / "pv", pkg_with_ref / "pv")
    shutil.copytree(toy_pkg_src / "raw_pv", pkg_with_ref / "raw_pv")
    shutil.copytree(toy_pkg_src / "metadata", pkg_with_ref / "metadata")

    # 2. Add references/references.txt inside the copied package
    ref_dir = pkg_with_ref / "references"
    ref_dir.mkdir()
    ref_txt = ref_dir / "references.txt"
    ref_txt.write_text(
        "1. Smith et al., 2020. doi: 10.1002/adma.202000000\n"
        "2. Duplicate: doi: 10.1002/adma.202000000\n"
        "3. Malformed: doi: 10.99/invalid/doi\n"
        "4. Very short\n",
        encoding="utf-8"
    )

    output_dir = tmp_path / "outputs"

    # 3. Run review-package on the package with references
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            str(pkg_with_ref),
            "-o",
            str(output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    # Verify reference_scan output directory files are copied
    ref_jsonl = output_dir / "reference_scan" / "reference_anomalies.jsonl"
    ref_summary = output_dir / "reference_scan" / "reference_anomaly_summary.md"
    assert ref_jsonl.exists()
    assert ref_summary.exists()

    # Validate reference_anomalies.jsonl using validate-ledger
    validation_result = validate_ledger_file(ref_jsonl)
    assert validation_result.ok is True
    assert validation_result.records > 0

    # Read unified_evidence_index.jsonl
    index_jsonl = output_dir / "unified_evidence_index.jsonl"
    assert index_jsonl.exists()

    # Validate unified_evidence_index.jsonl using validate-ledger
    index_validation = validate_ledger_file(index_jsonl)
    assert index_validation.ok is True

    findings = []
    with open(index_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # Assert unified index contains reference_anomaly findings
    ref_findings = [f for f in findings if f.get("finding_category") == "reference_anomaly"]
    assert len(ref_findings) > 0

    # 4. Verify HTML dashboard rendering details
    dash_html = output_dir / "review_package_dashboard.html"
    assert dash_html.exists()
    dash_content = dash_html.read_text(encoding="utf-8")

    # Dedicated section exists
    assert "Reference / Bibliography Anomalies" in dash_content
    # Safe notice text is present
    assert "not proof of research misconduct" in dash_content
    assert "bibliographic integrity fingerprints" in dash_content
    # Wording for specific rule anomalies is present
    assert "missing_doi" in dash_content
    assert "malformed_doi" in dash_content
    assert "duplicate_reference" in dash_content
    # Safe report language mapping text is present
    assert "Candidate Bibliographic Signal" in dash_content

    # Ensure reference anomalies are rendered in reference cards, not duplicate normal cards
    # There should be exactly the correct number of reference anomaly cards, and none of them rendered as plain articles
    assert dash_content.count('class="reference-anomaly-card"') == len(ref_findings)


def test_review_package_reference_scan_no_bleed(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    shared_output_dir = tmp_path / "shared_output"

    # 1. Create a copy of the toy review package WITH references
    toy_pkg_src = project_root / "examples/toy_review_package"
    pkg_with_ref = tmp_path / "pkg_with_ref"
    pkg_with_ref.mkdir()
    shutil.copytree(toy_pkg_src / "images", pkg_with_ref / "images")
    shutil.copytree(toy_pkg_src / "tables", pkg_with_ref / "tables")
    shutil.copytree(toy_pkg_src / "pv", pkg_with_ref / "pv")
    shutil.copytree(toy_pkg_src / "raw_pv", pkg_with_ref / "raw_pv")
    shutil.copytree(toy_pkg_src / "metadata", pkg_with_ref / "metadata")

    ref_dir = pkg_with_ref / "references"
    ref_dir.mkdir()
    (ref_dir / "references.txt").write_text("Smith et al. doi: 10.1002/adma.202000000\n", encoding="utf-8")

    # Run review-package on pkg_with_ref first
    result_with = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            str(pkg_with_ref),
            "-o",
            str(shared_output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result_with.returncode == 0, result_with.stderr

    # Verify that reference scan outputs exist
    assert (shared_output_dir / "reference_scan" / "reference_anomalies.jsonl").exists()
    assert (shared_output_dir / "reference_scan" / "reference_anomaly_summary.md").exists()

    # Verify unified index has reference_anomaly
    index_with = shared_output_dir / "unified_evidence_index.jsonl"
    with open(index_with, "r", encoding="utf-8") as f:
        findings_with = [json.loads(line) for line in f if line.strip()]
    assert any(f.get("finding_category") == "reference_anomaly" for f in findings_with)

    # 2. Create a copy of the toy review package WITHOUT references
    pkg_no_ref = tmp_path / "pkg_no_ref"
    pkg_no_ref.mkdir()
    shutil.copytree(toy_pkg_src / "images", pkg_no_ref / "images")
    shutil.copytree(toy_pkg_src / "tables", pkg_no_ref / "tables")
    shutil.copytree(toy_pkg_src / "pv", pkg_no_ref / "pv")
    shutil.copytree(toy_pkg_src / "raw_pv", pkg_no_ref / "raw_pv")
    shutil.copytree(toy_pkg_src / "metadata", pkg_no_ref / "metadata")

    # Run review-package on pkg_no_ref using the SAME output directory
    result_no = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            str(pkg_no_ref),
            "-o",
            str(shared_output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result_no.returncode == 0, result_no.stderr

    # Verify reference scan outputs are deleted/cleaned up and DO NOT remain
    assert not (shared_output_dir / "reference_scan").exists()

    # Verify unified index DOES NOT contain reference_anomaly
    index_no = shared_output_dir / "unified_evidence_index.jsonl"
    with open(index_no, "r", encoding="utf-8") as f:
        findings_no = [json.loads(line) for line in f if line.strip()]
    assert not any(f.get("finding_category") == "reference_anomaly" for f in findings_no)

    # Verify no-ref package run DOES NOT contain Reference / Bibliography section in HTML
    dash_no = shared_output_dir / "review_package_dashboard.html"
    assert dash_no.exists()
    dash_no_content = dash_no.read_text(encoding="utf-8")
    assert "Reference / Bibliography Anomalies" not in dash_no_content
    assert "reference-anomaly-card" not in dash_no_content
