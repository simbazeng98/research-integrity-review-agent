from __future__ import annotations

import logging
from pathlib import Path

from integrity_agent.core.images.image_schema import ImageManifestItem
from integrity_agent.core.images.perceptual_hash import compute_dhash, compute_phash_fallback, hamming_distance
from integrity_agent.core.images.similarity_schema import ImageSimilarityCandidate

logger = logging.getLogger(__name__)


def detect_perceptual_similarity(
    items: list[ImageManifestItem],
    threshold: int = 6,
    hash_method: str = "dhash",
) -> tuple[list[ImageSimilarityCandidate], int]:
    """Analyze image manifest items and detect near-duplicate visual similarity candidates.

    Returns:
        A tuple of (candidate_pairs_list, exact_duplicates_skipped_count).
    """
    project_root = Path.cwd()
    encodings: dict[str, dict[str, str]] = {}

    # 1. Compute hash encodings for all items that do not have warnings
    for item in items:
        if item.warnings:
            # Skip corrupted/unreadable images
            continue

        # Resolve path
        abs_path = Path(item.relative_path)
        if not abs_path.is_absolute():
            abs_path = (project_root / item.relative_path).resolve()

        if not abs_path.exists():
            # Try prepending examples/toy_image_package/
            fallback_path = (project_root / "examples" / "toy_image_package" / item.relative_path).resolve()
            if fallback_path.exists():
                abs_path = fallback_path
            else:
                # Search recursively
                matches = list(project_root.rglob(f"**/{Path(item.relative_path).name}"))
                if matches:
                    abs_path = matches[0]
                else:
                    continue

        try:
            dhash_val = compute_dhash(abs_path)
            phash_val = compute_phash_fallback(abs_path)
            encodings[item.image_id] = {
                "dhash": dhash_val,
                "phash": phash_val,
            }
        except Exception as e:
            logger.warning("Failed to compute hash for %s: %s", item.image_id, e)

    candidates: list[ImageSimilarityCandidate] = []
    skipped_exact_duplicates = 0
    candidate_idx = 1

    # 2. Pairwise comparison
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            item_a = items[i]
            item_b = items[j]

            # Skip if either is missing hash encodings
            if item_a.image_id not in encodings or item_b.image_id not in encodings:
                continue

            # Check if they are exact duplicates by SHA256
            if item_a.sha256 == item_b.sha256 and item_a.sha256 not in ["", "unknown", None]:
                skipped_exact_duplicates += 1
                continue

            hash_a = encodings[item_a.image_id][hash_method]
            hash_b = encodings[item_b.image_id][hash_method]

            distance = hamming_distance(hash_a, hash_b)

            if distance <= threshold:
                candidate = ImageSimilarityCandidate(
                    candidate_id=f"IMG-SIM-{candidate_idx:03d}",
                    rule_id="image_perceptual_similarity_candidate",
                    image_id_a=item_a.image_id,
                    image_id_b=item_b.image_id,
                    relative_path_a=item_a.relative_path,
                    relative_path_b=item_b.relative_path,
                    hash_method=hash_method,
                    hamming_distance=distance,
                    threshold=threshold,
                    risk_level="medium",
                    safe_report_language=(
                        "Candidate visual similarity signal detected; verify whether reuse is expected, "
                        "disclosed, transformed, or part of figure assembly."
                    ),
                    alternative_explanations=[
                        "repeated control image",
                        "same acquisition field exported differently",
                        "resized/cropped duplicate export",
                        "intentionally reused schematic",
                        "visually similar but independent images",
                    ],
                    false_positive_risks=[
                        "small/simple synthetic images",
                        "low-texture microscopy fields",
                        "schematic figures",
                        "common scale bars or backgrounds",
                        "threshold sensitivity",
                    ],
                    manual_verification=[
                        "original unprocessed image files",
                        "acquisition metadata",
                        "figure legends",
                        "source data",
                        "author explanation",
                    ],
                    limitations=[
                        "checks only global layout similarity and may yield false positives on simple or patterned images."
                    ],
                )
                candidates.append(candidate)
                candidate_idx += 1

    return candidates, skipped_exact_duplicates
