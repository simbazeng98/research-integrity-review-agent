from __future__ import annotations

from pathlib import Path
from PIL import Image


def _flattened_pixels(image: Image.Image) -> list[int]:
    """Return grayscale pixel values without Pillow 14 getdata deprecation noise."""
    get_flattened_data = getattr(image, "get_flattened_data", None)
    if callable(get_flattened_data):
        return list(get_flattened_data())
    return list(image.getdata())


def compute_dhash(image_path: Path | str, hash_size: int = 8) -> str:
    """Compute the difference hash (dHash) of an image file.

    Resizes the image to (hash_size + 1, hash_size), converts to grayscale,
    and compares adjacent pixels row-by-row.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(image_path) as img:
        # Convert to grayscale and resize
        img_gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
        pixels = _flattened_pixels(img_gray)

        diff = []
        for row in range(hash_size):
            for col in range(hash_size):
                left = pixels[row * (hash_size + 1) + col]
                right = pixels[row * (hash_size + 1) + col + 1]
                diff.append(left > right)

        # Convert bits to a hexadecimal string
        decimal_val = 0
        for bit in diff:
            decimal_val = (decimal_val << 1) | int(bit)

        # Output format is padded hex string (16 chars for 8x8)
        hex_len = (hash_size * hash_size) // 4
        return f"{decimal_val:0{hex_len}x}"


def compute_phash_fallback(image_path: Path | str, hash_size: int = 8) -> str:
    """Compute average hash (aHash) as the lightweight pure-Python fallback for pHash.

    Resizes the image to (hash_size, hash_size), converts to grayscale,
    and sets each bit based on whether the pixel exceeds the average intensity.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(image_path) as img:
        img_gray = img.convert("L").resize((hash_size, hash_size), Image.Resampling.BILINEAR)
        pixels = _flattened_pixels(img_gray)

        avg = sum(pixels) / len(pixels) if pixels else 0
        diff = [p >= avg for p in pixels]

        decimal_val = 0
        for bit in diff:
            decimal_val = (decimal_val << 1) | int(bit)

        hex_len = (hash_size * hash_size) // 4
        return f"{decimal_val:0{hex_len}x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Calculate the Hamming distance (number of differing bits) between two hex hashes."""
    if len(hash_a) != len(hash_b):
        raise ValueError(f"Hash lengths must be equal for Hamming distance comparison ({len(hash_a)} vs {len(hash_b)})")

    val_a = int(hash_a, 16)
    val_b = int(hash_b, 16)
    return bin(val_a ^ val_b).count("1")
