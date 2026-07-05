from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

from integrity_agent.workflows.report_image_similarity_pairs import generate_similarity_pairs_html


def test_generate_similarity_pairs_html(tmp_path):
    candidates_jsonl = tmp_path / "candidates.jsonl"
    html_file = tmp_path / "similarity_pairs.html"
    
    mock_candidates = [
        {
            "candidate_id": "IMG-SIM-001",
            "rule_id": "image_perceptual_similarity_candidate",
            "image_id_a": "img-001",
            "image_id_b": "img-002",
            "relative_path_a": "examples/toy_image_package/images/img_a.png",
            "relative_path_b": "examples/toy_image_package/images/img_c_brightness.png",
            "hash_method": "dhash",
            "hamming_distance": 2,
            "threshold": 6,
            "risk_level": "medium",
            "safe_report_language": "Candidate visual similarity signal detected."
        }
    ]
    
    # Write mock candidates
    with candidates_jsonl.open("w", encoding="utf-8") as f:
        for c in mock_candidates:
            f.write(json.dumps(c) + "\n")
            
    out_path = generate_similarity_pairs_html(candidates_jsonl, output_path=html_file)
    assert out_path.exists()
    
    html_content = out_path.read_text(encoding="utf-8")
    
    # 1. Verify safety disclaimer notice is present
    assert "This report shows candidate visual similarity pairs only and does not determine image manipulation or research misconduct." in html_content
    
    # 2. Verify candidate information
    assert "IMG-SIM-001" in html_content
    assert "img-001" in html_content
    assert "img-002" in html_content
    assert "dhash" in html_content
    assert "Hamming Distance: <strong>2</strong>" in html_content
    assert "threshold: 6" in html_content


def test_similarity_pairs_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    
    candidates_jsonl = project_root / "outputs" / "image_intake" / "image_similarity_candidates.jsonl"
    html_path = tmp_path / "similarity_pairs_test.html"
    
    # Run CLI command
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "report-image-similarity-pairs",
            str(candidates_jsonl),
            "-o",
            str(html_path)
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, result.stderr
    assert html_path.exists()
    
    content = html_path.read_text(encoding="utf-8")
    assert "This report shows candidate visual similarity pairs only and does not determine image manipulation or research misconduct." in content
