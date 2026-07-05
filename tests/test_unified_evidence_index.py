from __future__ import annotations

import json
from pathlib import Path

def test_unified_evidence_index_contents():
    project_root = Path(__file__).resolve().parents[1]
    index_path = project_root / "outputs" / "review_package_test" / "unified_evidence_index.jsonl"
    
    # Run CLI first if it wasn't run
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
        
    assert index_path.exists()
    
    findings = []
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))
                
    assert len(findings) > 0
    
    # Check that each finding preserves required keys
    for f in findings:
        assert "rule_id" in f
        assert "risk_level" in f
        assert "safe_report_language" in f
        assert "manual_verification" in f or "missing_verification_materials" in f or "suggested_verification_questions" in f
        
        # Verify source file is tracked
        src = f.get("source_file") or f.get("relative_path") or f.get("relative_path_a")
        if not src and f.get("evidence_items"):
            src = f["evidence_items"][0].get("source") or f["evidence_items"][0].get("relative_path")
        assert src is not None, f"Finding missing source tracking: {f}"
