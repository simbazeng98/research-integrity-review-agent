from __future__ import annotations

from integrity_agent.core.images.image_schema import ImageManifestItem, ImagePackageManifest, ImageEvidenceFinding


def test_image_manifest_item_to_dict():
    item = ImageManifestItem(
        image_id="img-01",
        source_file="test_folder",
        relative_path="img1.png",
        file_name="img1",
        file_ext=".png",
        file_size_bytes=1024,
        sha256="abc123sha",
        width=100,
        height=100,
        mode="RGB",
        format="PNG",
        warnings=["Some warn"]
    )
    
    d = item.to_dict()
    assert d["image_id"] == "img-01"
    assert d["sha256"] == "abc123sha"
    assert d["warnings"] == ["Some warn"]
    assert d["page_number"] is None


def test_image_package_manifest_to_dict():
    item = ImageManifestItem(
        image_id="img-01",
        source_file="test_folder",
        relative_path="img1.png",
        file_name="img1",
        file_ext=".png",
        file_size_bytes=1024,
        sha256="abc123sha",
        width=100,
        height=100,
        mode="RGB",
        format="PNG"
    )
    
    manifest = ImagePackageManifest(
        package_path="test_folder",
        total_images=1,
        items=[item]
    )
    
    d = manifest.to_dict()
    assert d["total_images"] == 1
    assert len(d["items"]) == 1
    assert d["items"][0]["image_id"] == "img-01"


def test_image_evidence_finding_to_dict():
    finding = ImageEvidenceFinding(
        finding_id="IMG-ERR-001",
        rule_id="image_exact_duplicate_sha256",
        risk_level="medium",
        evidence_items=[{"path": "img1.png"}],
        safe_report_language="Duplicate files detected",
        alternative_explanations=["Expected control"],
        manual_verification=["Legend review"]
    )
    
    d = finding.to_dict()
    assert d["finding_id"] == "IMG-ERR-001"
    assert len(d["evidence_items"]) == 1
    assert d["safe_report_language"] == "Duplicate files detected"
