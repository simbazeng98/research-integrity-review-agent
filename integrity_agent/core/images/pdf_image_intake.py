from __future__ import annotations

from importlib import import_module
from pathlib import Path

from integrity_agent.core.images.image_schema import ImageManifestItem


def extract_images_from_pdf(
    pdf_path: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[list[ImageManifestItem], list[str]]:
    """Extract embedded images from a PDF file.

    Stub implementation returning a clear warning if PyMuPDF (fitz) is not installed.
    Handles warnings gracefully without crashing the pipeline.

    Challenges in future PDF extraction:
    1. Repeated xrefs: Multiple pages might reference the exact same image object.
    2. Pseudo-images: Some images are just decorations, logos, or tiny stencil masks.
    3. Stencil masks: Color maps and transparency masks are stored as separate image xrefs.
    4. panel segmentation: Single figures containing multiple sub-panels (A, B, C)
       typically require layout analysis rather than raw stream extraction.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    warnings: list[str] = []
    items: list[ImageManifestItem] = []

    try:
        import_module("fitz")
    except ImportError:
        warnings.append("pymupdf_not_installed")
        return items, warnings

    # TODO: Implement PyMuPDF extraction when fitz is installed.
    # When implemented, this will loop over pages, locate image objects (xrefs),
    # extract pixel bytes, save as PNG/JPG, and return ImageManifestItem records.
    warnings.append("pdf_extraction_stub_active")
    return items, warnings
