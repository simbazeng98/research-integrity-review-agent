from __future__ import annotations

import pytest

from integrity_agent.core.metadata.doi import normalize_doi


def test_normalize_doi_valid():
    assert normalize_doi("10.1000/xyz123") == "10.1000/xyz123"
    assert normalize_doi("https://doi.org/10.1000/xyz123") == "10.1000/xyz123"
    assert normalize_doi("http://doi.org/10.1000/xyz123") == "10.1000/xyz123"
    assert normalize_doi("doi:10.1000/xyz123") == "10.1000/xyz123"


def test_normalize_doi_whitespace_and_punctuation():
    assert normalize_doi("  10.1000/xyz123  ") == "10.1000/xyz123"
    assert normalize_doi("10.1000/xyz123\n") == "10.1000/xyz123"
    assert normalize_doi("\tdoi:10.1000/xyz123\r\n") == "10.1000/xyz123"
    assert normalize_doi("10.1000/xyz123.") == "10.1000/xyz123"
    assert normalize_doi("10.1000/xyz123...") == "10.1000/xyz123"
    assert normalize_doi(" https://doi.org/10.1000/xyz123. ") == "10.1000/xyz123"


def test_normalize_doi_case_insensitivity():
    assert normalize_doi("DOI:10.1000/XYZ123") == "10.1000/xyz123"
    assert normalize_doi("HTTPS://DOI.ORG/10.1000/xyz") == "10.1000/xyz"


def test_normalize_doi_invalid():
    with pytest.raises(ValueError, match="must be a non-empty string"):
        normalize_doi("")

    with pytest.raises(ValueError, match="must be a non-empty string"):
        normalize_doi(None)  # type: ignore

    with pytest.raises(ValueError, match="Invalid DOI prefix"):
        normalize_doi("9.1000/xyz123")

    with pytest.raises(ValueError, match="Invalid DOI prefix"):
        normalize_doi("doi:9.1000/xyz123")
