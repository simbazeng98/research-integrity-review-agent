from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_jv_recalculate_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "jv-recalculate",
            "examples/toy_raw_pv_package/jv",
            "--reported",
            "examples/toy_raw_pv_package/reported/toy_reported_metrics.csv",
            "-o",
            "outputs/raw_pv_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    curves = project_root / "outputs" / "raw_pv_test" / "jv_curves.jsonl"
    metrics = project_root / "outputs" / "raw_pv_test" / "jv_metrics.jsonl"
    hysteresis = project_root / "outputs" / "raw_pv_test" / "jv_hysteresis_findings.jsonl"
    reconciliation = project_root / "outputs" / "raw_pv_test" / "jv_reconciliation_findings.jsonl"
    summary = project_root / "outputs" / "raw_pv_test" / "jv_recalculation_summary.md"
    
    assert curves.exists()
    assert metrics.exists()
    assert hysteresis.exists()
    assert reconciliation.exists()
    assert summary.exists()
