from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_image_similarity_cli():
    project_root = Path(__file__).resolve().parents[1]
    
    # 1. First run image intake to get manifest
    result_intake = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "image-intake",
            "examples/toy_image_package/images",
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result_intake.returncode == 0, result_intake.stderr
    
    manifest_jsonl = project_root / "outputs" / "image_intake" / "image_manifest.jsonl"
    assert manifest_jsonl.exists()
    
    # 2. Run image-similarity
    result_sim = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "image-similarity",
            str(manifest_jsonl),
            "--threshold", "6",
            "--hash-method", "dhash"
        ],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    assert result_sim.returncode == 0, result_sim.stderr
    
    hashes_jsonl = project_root / "outputs" / "image_intake" / "image_hashes.jsonl"
    candidates_jsonl = project_root / "outputs" / "image_intake" / "image_similarity_candidates.jsonl"
    summary_md = project_root / "outputs" / "image_intake" / "image_similarity_summary.md"
    
    assert hashes_jsonl.exists()
    assert candidates_jsonl.exists()
    assert summary_md.exists()
    
    # Check hashes file
    hashes = []
    with hashes_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                hashes.append(json.loads(line))
    assert len(hashes) == 5 # 5 valid images (corrupt skipped)
    assert hashes[0]["dhash"] is not None
    
    # Check candidates file
    candidates = []
    with candidates_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))
    assert len(candidates) >= 1
    assert candidates[0]["rule_id"] == "image_perceptual_similarity_candidate"
    assert candidates[0]["hash_method"] == "dhash"
    assert candidates[0]["hamming_distance"] <= 6
    
    # Check summary contains safe notice
    summary_text = summary_md.read_text(encoding="utf-8")
    assert "visually similar candidate pairs for human review" in summary_text
    assert "does not determine image manipulation" in summary_text
