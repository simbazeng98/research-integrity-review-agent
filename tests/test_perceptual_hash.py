from __future__ import annotations

import pytest
from pathlib import Path

from integrity_agent.core.images.perceptual_hash import compute_dhash, compute_phash_fallback, hamming_distance


def test_hamming_distance():
    # 0b0000 (0x0) vs 0b0000 (0x0)
    assert hamming_distance("0", "0") == 0
    # 0b1111 (0xf) vs 0b0000 (0x0)
    assert hamming_distance("f", "0") == 4
    # 0b1010 (0xa) vs 0b0101 (0x5)
    assert hamming_distance("a", "5") == 4
    
    with pytest.raises(ValueError):
        hamming_distance("a", "aa")


def test_compute_hashes_on_toy_fixtures():
    project_root = Path(__file__).resolve().parents[1]
    img_a = project_root / "examples" / "toy_image_package" / "images" / "img_a.png"
    img_b = project_root / "examples" / "toy_image_package" / "images" / "img_b.png"
    img_copy = project_root / "examples" / "toy_image_package" / "images" / "img_a_copy.png"
    
    # Calculate dHash
    hash_a = compute_dhash(img_a)
    hash_b = compute_dhash(img_b)
    hash_copy = compute_dhash(img_copy)
    
    assert len(hash_a) == 16
    assert hash_a == hash_copy
    assert hash_a != hash_b
    assert hamming_distance(hash_a, hash_copy) == 0
    assert hamming_distance(hash_a, hash_b) > 0

    # Calculate pHash fallback
    phash_a = compute_phash_fallback(img_a)
    phash_b = compute_phash_fallback(img_b)
    phash_copy = compute_phash_fallback(img_copy)
    
    assert len(phash_a) == 16
    assert phash_a == phash_copy
    assert phash_a != phash_b
    assert hamming_distance(phash_a, phash_copy) == 0
    assert hamming_distance(phash_a, phash_b) > 0
