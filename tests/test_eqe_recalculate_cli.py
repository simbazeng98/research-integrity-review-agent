from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_eqe_recalculate_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "eqe-recalculate",
            "examples/toy_raw_pv_package/eqe",
            "--reference",
            "examples/toy_raw_pv_package/reference/toy_am15g.csv",
            "--reported",
            "examples/toy_raw_pv_package/reported/toy_reported_metrics.csv",
            "--jv-metrics",
            "outputs/raw_pv_test/jv_metrics.jsonl",
            "-o",
            "outputs/raw_pv_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    spectra = project_root / "outputs" / "raw_pv_test" / "eqe_spectra.jsonl"
    integration = project_root / "outputs" / "raw_pv_test" / "eqe_integration_results.jsonl"
    reconciliation = project_root / "outputs" / "raw_pv_test" / "eqe_reconciliation_findings.jsonl"
    summary = project_root / "outputs" / "raw_pv_test" / "eqe_recalculation_summary.md"
    
    assert spectra.exists()
    assert integration.exists()
    assert reconciliation.exists()
    assert summary.exists()
