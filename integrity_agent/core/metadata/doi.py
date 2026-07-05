from __future__ import annotations

import re


def normalize_doi(raw: str) -> str:
    """Normalize a raw DOI string into a canonical 10.xxxx/yyyy format.

    Supports:
      - 10.xxxx/yyyy
      - https://doi.org/10.xxxx/yyyy
      - doi:10.xxxx/yyyy
      - Leading/trailing whitespace, newlines, and trailing punctuation (like periods).
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("DOI must be a non-empty string")

    # Remove all whitespace characters (spaces, tabs, newlines)
    s = "".join(raw.split())

    # Remove URL prefixes or 'doi:' protocol prefixes case-insensitively
    s = re.sub(r"^(https?://(?:dx\.)?doi\.org/|doi:)", "", s, flags=re.IGNORECASE)

    # Remove trailing periods which are common sentence-ending punctuation
    s = re.sub(r"\.+$", "", s)

    if not s.startswith("10."):
        raise ValueError(f"Invalid DOI prefix (must start with '10.'): {raw}")

    # Canonical DOI is lowercase for the authority prefix, but we lowercase the whole DOI
    # as Crossref API is case-insensitive for lookup and registration.
    return s.lower()
