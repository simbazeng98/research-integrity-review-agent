from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_raw_pv_intake_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "raw-pv-intake",
            "examples/toy_raw_pv_package",
            "-o",
            "outputs/raw_pv_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    manifest = project_root / "outputs" / "raw_pv_test" / "raw_pv_manifest.jsonl"
    summary = project_root / "outputs" / "raw_pv_test" / "raw_pv_intake_summary.md"
    
    assert manifest.exists()
    assert summary.exists()
    
    content = manifest.read_text(encoding="utf-8")
    assert "jv/dev1_fwd.csv" in content
    assert "eqe/dev1_eqe.csv" in content
    assert "excel/toy_sheet.xlsx" in content
