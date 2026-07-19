from __future__ import annotations

import csv
import json
from pathlib import Path

from integrity_agent.core.images.image_schema import ImageEvidenceFinding, ImageManifestItem
from integrity_agent.core.images.folder_intake import intake_image_folder
from integrity_agent.core.output_safety import sanitize_csv_cell
from integrity_agent.detectors.image.exact_duplicate import detect_exact_duplicates

DEFAULT_OUTPUT_DIR = Path("outputs") / "image_intake"


def _write_manifest_csv(path: Path, items: list[ImageManifestItem]) -> None:
    headers = [
        "image_id",
        "source_file",
        "relative_path",
        "file_name",
        "file_ext",
        "file_size_bytes",
        "sha256",
        "width",
        "height",
        "mode",
        "format",
        "warnings",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in items:
            writer.writerow(
                [
                    sanitize_csv_cell(value)
                    for value in [
                        item.image_id,
                        item.source_file,
                        item.relative_path,
                        item.file_name,
                        item.file_ext,
                        item.file_size_bytes,
                        item.sha256,
                        item.width,
                        item.height,
                        item.mode,
                        item.format,
                        "; ".join(item.warnings),
                    ]
                ]
            )


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _generate_image_summary_md(
    path: Path,
    folder_name: str,
    items: list[ImageManifestItem],
    findings: list[ImageEvidenceFinding],
) -> None:
    total_images = len(items)

    # Count unique valid hashes
    hashes = [
        item.sha256 for item in items
        if item.sha256 and item.sha256 != "unknown" and not item.sha256.startswith("error")
    ]
    unique_hashes = len(set(hashes))

    lines = [
        "# Image Intake Summary Report",
        "",
        "## Source package",
        f"- Target folder: `{folder_name}`",
        "",
        "## Statistics",
        f"- Total image files: {total_images}",
        f"- Unique image hashes: {unique_hashes}",
        f"- Risk findings detected: {len(findings)}",
        "",
        "## Detected risk signals",
    ]

    if findings:
        for f in findings:
            lines.append(f"- `{f.rule_id}` ({f.risk_level}): {f.safe_report_language}")
            lines.append("  - Evidences:")
            for ev in f.evidence_items:
                lines.append(f"    - Image `{ev['image_id']}` | File: `{ev['relative_path']}`")
    else:
        lines.append("- No image risk signals detected.")

    lines.extend([
        "",
        "## Alternative benign explanations",
        "- Repeated control/loading images may be intentionally reused across figures.",
        "- Reused schematics, illustrations, or legends describing duplicate experimental setups.",
        "- Duplicated exports or file-system copies created during image folder preparation.",
        "- Synthetic toy fixtures generated for code testing.",
        "",
        "## Missing verification materials",
        "- Raw, uncropped, high-resolution original acquisition files (e.g. TIF, TIFF).",
        "- Instrument export acquisition metadata (timestamps, settings).",
        "- Figure legends describing whether panels contain reused or duplicated components.",
        "- Author explanations regarding the reuse or assembly of the figures.",
        "",
        "## Suggested verification questions",
        "- Please provide the original, uncropped acquisition files and camera export metadata.",
        "- Please clarify whether the duplicate panels represent the same experimental run or different controls.",
        "- Please confirm that figure assembly and panel reuse conform to the publisher guidelines.",
        "",
        "## Limitations",
        "- This detector checks only exact duplicates by SHA256 file-level hashing.",
        "- It does not perform near-duplicate, pHash, SSIM, ORB, copy-move, or ELA image analysis.",
        "- Extracting images from PDF is a stub and does not segment sub-panels automatically.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces image file-level metadata signals for human review. It does not determine image manipulation, intent, or research misconduct.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def run_image_intake(
    folder_path: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Execute the image intake, metadata scan, and exact duplicate detection workflow."""
    folder_path = Path(folder_path)
    if not folder_path.exists():
        raise FileNotFoundError(f"Image folder not found: {folder_path}")

    # 1. Intake image folder
    items = intake_image_folder(folder_path)

    # 2. Run exact duplicate detector
    findings = detect_exact_duplicates(items)

    # 3. Resolve output folder
    if output_dir is None:
        resolved_out = DEFAULT_OUTPUT_DIR
    else:
        resolved_out = Path(output_dir)

    resolved_out.mkdir(parents=True, exist_ok=True)

    manifest_jsonl = resolved_out / "image_manifest.jsonl"
    manifest_csv = resolved_out / "image_manifest.csv"
    findings_jsonl = resolved_out / "image_findings.jsonl"
    summary_md = resolved_out / "image_intake_summary.md"

    # 4. Write output files
    _write_jsonl(manifest_jsonl, [item.to_dict() for item in items])
    _write_manifest_csv(manifest_csv, items)
    _write_jsonl(findings_jsonl, [finding.to_dict() for finding in findings])
    _generate_image_summary_md(summary_md, folder_path.name, items, findings)

    return (
        manifest_jsonl.resolve(),
        manifest_csv.resolve(),
        findings_jsonl.resolve(),
        summary_md.resolve(),
    )
