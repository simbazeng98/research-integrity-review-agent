from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_excel_formula_audit_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "excel-formula-audit",
            "examples/toy_raw_pv_package/excel",
            "-o",
            "outputs/raw_pv_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    audit_log = project_root / "outputs" / "raw_pv_test" / "excel_formula_audit.jsonl"
    summary = project_root / "outputs" / "raw_pv_test" / "excel_formula_audit_summary.md"
    
    assert audit_log.exists()
    assert summary.exists()
