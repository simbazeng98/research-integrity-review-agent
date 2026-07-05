from __future__ import annotations

import json
from pathlib import Path

FORBIDDEN_PHRASES = [
    "造假成立",
    "学术不端成立",
    "作者造假",
    "fraud confirmed",
    "misconduct confirmed"
]

def test_review_package_safety_language():
    project_root = Path(__file__).resolve().parents[1]
    pkg_test_dir = project_root / "outputs" / "review_package_test"
    
    # Run CLI first if it wasn't run
    index_path = pkg_test_dir / "unified_evidence_index.jsonl"
    if not index_path.exists():
        import subprocess
        import sys
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

    # 1. Check index file
    assert index_path.exists()
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                finding = json.loads(line)
                
                # Check risk level ceiling
                assert finding.get("risk_level", "low").lower() in ("low", "medium"), \
                    f"Risk level ceiling exceeded in finding: {finding}"
                
                # Check safe report language
                safe_lang = finding.get("safe_report_language", "").lower()
                for phrase in FORBIDDEN_PHRASES:
                    assert phrase not in safe_lang, \
                        f"Forbidden overclaiming phrase '{phrase}' found in finding safe language: {safe_lang}"

    # 2. Check summary report
    summary_path = pkg_test_dir / "review_package_summary.md"
    assert summary_path.exists()
    summary_content = summary_path.read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in summary_content, \
            f"Forbidden overclaiming phrase '{phrase}' found in summary report: {summary_content}"

    # 3. Check HTML dashboard
    html_path = pkg_test_dir / "review_package_dashboard.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in html_content, \
            f"Forbidden overclaiming phrase '{phrase}' found in HTML dashboard: {html_content}"
