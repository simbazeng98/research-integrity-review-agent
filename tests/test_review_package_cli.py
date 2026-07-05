from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_review_package_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            "examples/toy_review_package",
            "-o",
            "outputs/review_package_test"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    
    manifest_json = project_root / "outputs" / "review_package_test" / "review_package_manifest.json"
    module_status_jsonl = project_root / "outputs" / "review_package_test" / "module_status.jsonl"
    index_jsonl = project_root / "outputs" / "review_package_test" / "unified_evidence_index.jsonl"
    summary_md = project_root / "outputs" / "review_package_test" / "review_package_summary.md"
    dashboard_html = project_root / "outputs" / "review_package_test" / "review_package_dashboard.html"
    
    assert manifest_json.exists()
    assert module_status_jsonl.exists()
    assert index_jsonl.exists()
    assert summary_md.exists()
    assert dashboard_html.exists()
