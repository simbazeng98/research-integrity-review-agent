from __future__ import annotations

import json
from pathlib import Path

from integrity_agent.core.images.image_schema import ImageManifestItem
from integrity_agent.core.images.perceptual_hash import compute_dhash, compute_phash_fallback
from integrity_agent.core.images.similarity_schema import (
    ImageHashEncoding,
    ImageSimilarityRunSummary,
)
from integrity_agent.detectors.image.perceptual_similarity import detect_perceptual_similarity

DEFAULT_OUTPUT_DIR = Path("outputs") / "image_intake"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _generate_similarity_summary_md(
    path: Path,
    summary: ImageSimilarityRunSummary,
) -> None:
    lines = [
        "# Image Similarity Review Summary",
        "",
        "## Configuration",
        f"- Hash method: `{summary.hash_method}`",
        f"- Hamming distance threshold: {summary.threshold}",
        "",
        "## Statistics",
        f"- Number of images processed: {summary.total_images}",
        f"- Number of candidate similarity pairs: {summary.candidate_pairs_count}",
        f"- Exact duplicate pairs (SHA256 identical) skipped: {summary.exact_duplicates_skipped}",
        "",
        "## Visual Similarity Candidate Pairs",
    ]

    if summary.candidates:
        for c in summary.candidates:
            lines.append(f"- Candidate `{c.candidate_id}`:")
            lines.append(f"  - Image A: `{c.image_id_a}` (`{c.relative_path_a}`)")
            lines.append(f"  - Image B: `{c.image_id_b}` (`{c.relative_path_b}`)")
            lines.append(f"  - Hamming distance: {c.hamming_distance}")
    else:
        lines.append("- No visual similarity candidates detected within the specified threshold.")

    lines.extend([
        "",
        "## Limitations",
        "- Perceptual hashing calculates global visual layout and contrast gradients.",
        "- It cannot guarantee detection of all copy-move, noise inconsistencies, or local edits.",
        "- Simple synthetic borders, scale bars, or low-texture microscopy fields may cause false positives.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces visually similar candidate pairs for human review. It does not determine image manipulation, intent, or research misconduct.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def run_image_similarity(
    manifest_jsonl_path: Path | str,
    output_dir: Path | str | None = None,
    threshold: int = 6,
    hash_method: str = "dhash",
) -> tuple[Path, Path, Path]:
    """Execute the image similarity workflow, computing hashes and detecting candidates."""
    manifest_jsonl_path = Path(manifest_jsonl_path)
    if not manifest_jsonl_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_jsonl_path}")

    # 1. Parse manifest items
    items = []
    with manifest_jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(ImageManifestItem(**json.loads(line)))

    # 2. Compute encodings
    encodings: list[ImageHashEncoding] = []
    project_root = Path.cwd()

    for item in items:
        if item.warnings:
            continue

        abs_path = Path(item.relative_path)
        if not abs_path.is_absolute():
            abs_path = (project_root / item.relative_path).resolve()

        if not abs_path.exists():
            # Try fallback search under examples/
            fallback = (project_root / "examples" / "toy_image_package" / item.relative_path).resolve()
            if fallback.exists():
                abs_path = fallback
            else:
                matches = list(project_root.rglob(f"**/{Path(item.relative_path).name}"))
                if matches:
                    abs_path = matches[0]
                else:
                    continue

        try:
            dhash_val = compute_dhash(abs_path)
            phash_val = compute_phash_fallback(abs_path)
            encodings.append(
                ImageHashEncoding(
                    image_id=item.image_id,
                    relative_path=item.relative_path,
                    dhash=dhash_val,
                    phash=phash_val,
                )
            )
        except Exception:
            # Skip errors
            pass

    # 3. Detect candidates
    candidates, skipped_exact = detect_perceptual_similarity(items, threshold, hash_method)

    # 4. Resolve output dir
    if output_dir is None:
        resolved_out = DEFAULT_OUTPUT_DIR
    else:
        resolved_out = Path(output_dir)

    resolved_out.mkdir(parents=True, exist_ok=True)

    hashes_path = resolved_out / "image_hashes.jsonl"
    candidates_path = resolved_out / "image_similarity_candidates.jsonl"
    summary_path = resolved_out / "image_similarity_summary.md"

    # Write files
    _write_jsonl(hashes_path, [enc.to_dict() for enc in encodings])
    _write_jsonl(candidates_path, [cand.to_dict() for cand in candidates])

    summary_obj = ImageSimilarityRunSummary(
        hash_method=hash_method,
        threshold=threshold,
        total_images=len(items),
        candidate_pairs_count=len(candidates),
        exact_duplicates_skipped=skipped_exact,
        candidates=candidates,
    )
    _generate_similarity_summary_md(summary_path, summary_obj)

    return hashes_path.resolve(), candidates_path.resolve(), summary_path.resolve()
