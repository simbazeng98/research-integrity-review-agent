from __future__ import annotations

from pathlib import Path

from integrity_agent.core.images.folder_intake import intake_image_folder
from integrity_agent.detectors.image.perceptual_similarity import detect_perceptual_similarity


def test_detect_perceptual_similarity():
    project_root = Path(__file__).resolve().parents[1]
    folder_path = project_root / "examples" / "toy_image_package" / "images"
    
    # 1. Gather folder images
    items = intake_image_folder(folder_path)
    # 6 images expected: img_a, img_b, img_a_copy, img_c_brightness, img_d_crop, img_corrupt
    assert len(items) == 6
    
    # 2. Run similarity detector with default threshold=6
    candidates, skipped_exact = detect_perceptual_similarity(items, threshold=6)
    
    # Verify exact duplicate (img_a vs img_a_copy) was skipped
    assert skipped_exact == 1
    
    # Verify similarity candidates detected
    # Should find img_a vs img_c_brightness (darker red square) or img_a vs img_d_crop
    assert len(candidates) >= 1
    
    candidate = candidates[0]
    assert candidate.rule_id == "image_perceptual_similarity_candidate"
    assert candidate.hash_method == "dhash"
    assert candidate.hamming_distance <= 6
    assert "visual similarity" in candidate.safe_report_language
    assert "repeated control image" in candidate.alternative_explanations
    assert "schematic figures" in candidate.false_positive_risks
    
    # Verify img_a vs img_b (red box vs green circle) is not a candidate
    # (since their distance is high)
    for c in candidates:
        pair_ids = {c.image_id_a, c.image_id_b}
        # Find if img_a vs img_b got paired
        img_a_id = next(x.image_id for x in items if x.file_name == "img_a")
        img_b_id = next(x.image_id for x in items if x.file_name == "img_b")
        assert not ({img_a_id, img_b_id} <= pair_ids)
