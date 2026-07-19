from __future__ import annotations

from integrity_agent.core.images.image_schema import ImageManifestItem
from integrity_agent.detectors.image.exact_duplicate import detect_exact_duplicates


def test_detect_exact_duplicates_no_dups():
    items = [
        ImageManifestItem(
            image_id="img-01",
            source_file="f",
            relative_path="p1.png",
            file_name="p1",
            file_ext=".png",
            file_size_bytes=10,
            sha256="hash-1",
            width=10, height=10, mode="RGB", format="PNG"
        ),
        ImageManifestItem(
            image_id="img-02",
            source_file="f",
            relative_path="p2.png",
            file_name="p2",
            file_ext=".png",
            file_size_bytes=15,
            sha256="hash-2",
            width=10, height=10, mode="RGB", format="PNG"
        )
    ]
    findings = detect_exact_duplicates(items)
    assert len(findings) == 0


def test_detect_exact_duplicates_with_dups():
    items = [
        ImageManifestItem(
            image_id="img-01",
            source_file="f",
            relative_path="p1.png",
            file_name="p1",
            file_ext=".png",
            file_size_bytes=10,
            sha256="duplicate-hash",
            width=10, height=10, mode="RGB", format="PNG"
        ),
        ImageManifestItem(
            image_id="img-02",
            source_file="f",
            relative_path="p2.png",
            file_name="p2",
            file_ext=".png",
            file_size_bytes=10,
            sha256="duplicate-hash",
            width=10, height=10, mode="RGB", format="PNG"
        ),
        ImageManifestItem(
            image_id="img-03",
            source_file="f",
            relative_path="p3.png",
            file_name="p3",
            file_ext=".png",
            file_size_bytes=20,
            sha256="unique-hash",
            width=10, height=10, mode="RGB", format="PNG"
        )
    ]
    findings = detect_exact_duplicates(items)
    assert len(findings) == 1
    
    finding = findings[0]
    assert finding.finding_id == "IMG-DUP-001"
    assert finding.rule_id == "image_exact_duplicate_sha256"
    assert finding.risk_level == "medium"
    assert len(finding.evidence_items) == 2
    assert finding.evidence_items[0]["image_id"] == "img-01"
    assert finding.evidence_items[1]["image_id"] == "img-02"
    assert "Exact duplicate image" in finding.safe_report_language
    assert "repeated control image" in finding.alternative_explanations
    assert "original image files" in finding.manual_verification
    assert finding.metadata["detector_id"] == "image_exact_duplicate_sha256"
