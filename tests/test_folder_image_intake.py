from __future__ import annotations

import pytest
from pathlib import Path

from integrity_agent.core.images.folder_intake import intake_image_folder


def test_intake_image_folder():
    project_root = Path(__file__).resolve().parents[1]
    folder_path = project_root / "examples" / "toy_image_package" / "images"
    
    items = intake_image_folder(folder_path)
    
    # 6 images expected: img_a, img_b, img_a_copy, img_c_brightness, img_d_crop, img_corrupt
    assert len(items) == 6
    
    # Check img_a properties
    img_a = next(x for x in items if x.file_name == "img_a")
    assert img_a.width == 100
    assert img_a.height == 100
    assert img_a.mode == "RGB"
    assert img_a.format == "PNG"
    assert len(img_a.warnings) == 0
    assert len(img_a.sha256) == 64
    
    # Check img_a_copy has identical hash but different file name
    img_copy = next(x for x in items if x.file_name == "img_a_copy")
    assert img_copy.sha256 == img_a.sha256
    assert img_copy.width == 100
    
    # Check corrupt image properties and warnings
    img_corrupt = next(x for x in items if x.file_name == "img_corrupt")
    assert img_corrupt.width == 0
    assert img_corrupt.height == 0
    assert img_corrupt.format == "unknown"
    assert len(img_corrupt.warnings) == 1
    assert "Failed to read" in img_corrupt.warnings[0]


def test_extract_images_from_pdf_stub(tmp_path):
    from integrity_agent.core.images.pdf_image_intake import extract_images_from_pdf
    
    pdf_file = tmp_path / "mock.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 mock content")
    
    items, warnings = extract_images_from_pdf(pdf_file)
    assert len(items) == 0
    assert ("pymupdf_not_installed" in warnings) or ("pdf_extraction_stub_active" in warnings)

