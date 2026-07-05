from __future__ import annotations

from collections import defaultdict

from integrity_agent.core.images.image_schema import ImageEvidenceFinding, ImageManifestItem


def detect_exact_duplicates(items: list[ImageManifestItem]) -> list[ImageEvidenceFinding]:
    """Analyze image manifest items and detect exact duplicates based on SHA256."""
    groups = defaultdict(list)
    for item in items:
        # Ignore empty, unknown, or error hash values
        if item.sha256 and item.sha256 != "unknown" and not item.sha256.startswith("error"):
            groups[item.sha256].append(item)

    findings: list[ImageEvidenceFinding] = []
    finding_idx = 1

    for sha256_hash, group in groups.items():
        if len(group) > 1:
            evidence_items = [
                {
                    "image_id": item.image_id,
                    "relative_path": item.relative_path,
                    "file_name": item.file_name,
                    "file_ext": item.file_ext,
                    "file_size_bytes": item.file_size_bytes,
                }
                for item in group
            ]

            finding = ImageEvidenceFinding(
                finding_id=f"IMG-DUP-{finding_idx:03d}",
                rule_id="image_exact_duplicate_sha256",
                risk_level="medium",
                evidence_items=evidence_items,
                safe_report_language=(
                    "Exact duplicate image files detected; verify whether reuse is expected, "
                    "disclosed, or part of figure assembly."
                ),
                alternative_explanations=[
                    "repeated control image",
                    "intentionally reused schematic",
                    "duplicated export",
                    "toy duplicate fixture",
                ],
                manual_verification=[
                    "original image files",
                    "figure legends",
                    "source data / acquisition metadata",
                    "author explanation",
                ],
                metadata={
                    "detector_id": "image_exact_duplicate_sha256",
                    "runtime_status": "active",
                    "execution_mode": "offline",
                    "risk_ceiling": "medium",
                    "requires_network": False,
                    "requires_private_data": False,
                },
            )
            findings.append(finding)
            finding_idx += 1

    return findings
