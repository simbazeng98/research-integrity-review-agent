from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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

    candidates_jsonl = tmp_path / "candidates.jsonl"
    candidates_jsonl.write_text(
        json.dumps(
            {
                "candidate_id": "IMG-SIM-CLI-001",
                "image_id_a": "img-a",
                "image_id_b": "img-b",
                "relative_path_a": "images/a.png",
                "relative_path_b": "images/b.png",
                "hash_method": "dhash",
                "hamming_distance": 2,
                "threshold": 6,
            }
        )
        + "\n",
        encoding="utf-8",
    )
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


def test_similarity_pairs_escapes_text_and_image_attributes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    candidates_jsonl = tmp_path / "candidates.jsonl"
    html_file = tmp_path / "similarity_pairs.html"
    attack = 'photo" onerror="alert(1)'
    candidate = {
        "candidate_id": "</span><script>alert(1)</script>",
        "image_id_a": "</code><script>alert(1)</script>",
        "image_id_b": "img-safe",
        "relative_path_a": f"{attack}.png",
        "relative_path_b": "safe image.png",
        "hash_method": "dhash<script>",
        "hamming_distance": 2,
        "threshold": 6,
    }
    candidates_jsonl.write_text(json.dumps(candidate) + "\n", encoding="utf-8")

    out_path = generate_similarity_pairs_html(candidates_jsonl, output_path=html_file)
    content = out_path.read_text(encoding="utf-8")

    assert "<script>" not in content
    assert "%22%20onerror%3D%22alert%281%29.png" in content
    assert 'alt="photo&quot; onerror=&quot;alert(1).png"' in content


def test_similarity_pairs_does_not_embed_project_external_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    candidates_jsonl = tmp_path / "candidates.jsonl"
    html_file = tmp_path / "similarity_pairs.html"
    candidate = {
        "candidate_id": "external-path",
        "image_id_a": "img-a",
        "image_id_b": "img-b",
        "relative_path_a": r"D:\Private Folder\secret-a.png",
        "relative_path_b": r"D:\Private Folder\secret-b.png",
        "hash_method": "dhash",
        "hamming_distance": 2,
        "threshold": 6,
    }
    candidates_jsonl.write_text(json.dumps(candidate) + "\n", encoding="utf-8")

    generate_similarity_pairs_html(candidates_jsonl, output_path=html_file)
    content = html_file.read_text(encoding="utf-8")

    assert "Preview unavailable" in content
    assert "Private Folder" not in content
    assert "D:%5C" not in content
    assert "D:\\Private" not in content
