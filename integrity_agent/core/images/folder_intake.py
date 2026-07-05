from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from integrity_agent.core.images.image_schema import ImageManifestItem

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file efficiently by reading in chunks."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def intake_image_folder(folder_path: Path | str) -> list[ImageManifestItem]:
    """Scan the given folder for images and extract manifest metadata.

    Fails gracefully on corrupted images by logging warnings instead of crashing.
    """
    folder_path = Path(folder_path)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    # List and sort files for deterministic output ordering
    files = sorted([
        p for p in folder_path.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ])

    items: list[ImageManifestItem] = []
    source_file = folder_path.name

    for idx, p in enumerate(files, 1):
        image_id = f"img-{idx:03d}"
        file_name = p.stem
        file_ext = p.suffix
        # Use relative path from the parent of the folder to keep it descriptive
        relative_path = p.relative_to(folder_path.parent).as_posix()
        file_size_bytes = p.stat().st_size

        try:
            sha256 = calculate_sha256(p)
        except Exception as e:
            sha256 = f"error_calculating_hash: {e}"

        warnings: list[str] = []
        width = 0
        height = 0
        mode = "unknown"
        fmt = "unknown"

        try:
            with Image.open(p) as img:
                width = img.width
                height = img.height
                mode = img.mode
                fmt = img.format or p.suffix[1:].upper()
        except Exception as e:
            warnings.append(f"Failed to read image metadata: {e}")

        items.append(
            ImageManifestItem(
                image_id=image_id,
                source_file=source_file,
                relative_path=relative_path,
                file_name=file_name,
                file_ext=file_ext,
                file_size_bytes=file_size_bytes,
                sha256=sha256,
                width=width,
                height=height,
                mode=mode,
                format=fmt,
                warnings=warnings,
            )
        )

    return items
