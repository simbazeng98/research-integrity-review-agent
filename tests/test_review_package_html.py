from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def test_review_package_html_cli_run():
    project_root = Path(__file__).resolve().parents[1]
    index_path = project_root / "outputs" / "review_package_test" / "unified_evidence_index.jsonl"
    html_path = project_root / "outputs" / "review_package_test" / "review_package_dashboard_test.html"
    
    # Run CLI first if it wasn't run
    if not index_path.exists():
        subprocess.run(
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
            check=True
        )
        
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-review-package-html",
            str(index_path),
            "-o",
            str(html_path)
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, result.stderr
    assert html_path.exists()
    
    html_content = html_path.read_text(encoding="utf-8")
    assert "This dashboard aggregates evidence signals only and does not determine research misconduct." in html_content
    assert "Unified Research Integrity Review Dashboard" in html_content
