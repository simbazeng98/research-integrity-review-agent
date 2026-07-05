from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_raw_pv_reconciliation_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "raw-pv-reconcile",
            "examples/toy_raw_pv_package",
            "-o",
            "outputs/raw_pv_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    findings = project_root / "outputs" / "raw_pv_test" / "raw_pv_findings.jsonl"
    summary = project_root / "outputs" / "raw_pv_test" / "raw_pv_reconciliation_summary.md"
    
    assert findings.exists()
    assert summary.exists()
