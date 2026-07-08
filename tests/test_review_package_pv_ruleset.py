from __future__ import annotations

import json
import shutil
from pathlib import Path
import pytest

from integrity_agent.workflows.review_package import run_review_package
from integrity_agent.workflows.validate_ledger import validate_ledger_file

def test_review_package_pv_ruleset_integration(tmp_path):
    # 1. Create a package with a PV table
    pkg_dir = tmp_path / "toy_pkg"
    tables_dir = pkg_dir / "tables"
    tables_dir.mkdir(parents=True)

    csv_file = tables_dir / "toy_pv.csv"
    csv_content = (
        "Device ID,Voc (V),Jsc (mA/cm2),FF (%),PCE (%)\n"
        "device-1,1.10,22.0,75.0,18.15\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    out_dir = tmp_path / "outputs"

    # 2. Run review-package
    summary = run_review_package(
        package_dir=str(pkg_dir),
        output_dir=str(out_dir)
    )

    # 3. Assert outputs exist
    findings_file = out_dir / "pv_ruleset_review" / "pv_ruleset_findings.jsonl"
    summary_file = out_dir / "pv_ruleset_review" / "pv_ruleset_review_summary.md"
    assert findings_file.exists()
    assert summary_file.exists()

    # Load unified evidence index
    unified_file = out_dir / "unified_evidence_index.jsonl"
    assert unified_file.exists()

    unified_findings = []
    with unified_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                unified_findings.append(json.loads(line))

    # Assert unified findings contain pv_evidence_completeness
    pv_completeness = [f for f in unified_findings if f.get("finding_category") == "pv_evidence_completeness"]
    assert len(pv_completeness) > 0

    # Validate ledger schema
    val_res = validate_ledger_file(unified_file)
    assert len(val_res.issues) == 0, f"Unified ledger validation failed: {val_res.issues}"

    # 4. Now run on a package WITHOUT PV tables, reusing the same output folder
    pkg_dir_no_pv = tmp_path / "toy_pkg_no_pv"
    pkg_dir_no_pv.mkdir()
    (pkg_dir_no_pv / "tables").mkdir() # empty tables folder

    summary_no_pv = run_review_package(
        package_dir=str(pkg_dir_no_pv),
        output_dir=str(out_dir)
    )

    # Assert that the old pv_ruleset_review folder was cleaned up and is not present
    assert not (out_dir / "pv_ruleset_review").exists()

    # Load new unified index
    unified_findings_no_pv = []
    with unified_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                unified_findings_no_pv.append(json.loads(line))

    pv_completeness_no_pv = [f for f in unified_findings_no_pv if f.get("finding_category") == "pv_evidence_completeness"]
    assert len(pv_completeness_no_pv) == 0
