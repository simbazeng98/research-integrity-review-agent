from __future__ import annotations

import json
import pytest

from integrity_agent.core.metadata.crossref_client import (
    fetch_crossref_work,
    CrossrefClientError,
)


def test_fetch_crossref_work_from_mock_offline():
    # Toy retracted mock exists in local mock dict
    res = fetch_crossref_work("10.0000/toy-retracted", allow_network=False)
    assert res["status"] == "ok"
    assert res["message"]["DOI"] == "10.0000/toy-retracted"


def test_fetch_crossref_work_missing_offline_raises_error():
    # Unknown DOI without cache or mock raises error
    with pytest.raises(CrossrefClientError, match="Network lookup is disabled"):
        fetch_crossref_work("10.9999/unknown-doi", allow_network=False)


def test_fetch_crossref_work_reads_from_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    
    # Pre-populate cache file for an unknown DOI
    cached_data = {
        "status": "ok",
        "message": {
            "DOI": "10.9999/cached-doi",
            "title": ["Cached Metadata Title"]
        }
    }
    
    # Safe filename mapping uses safe characters
    cache_file = cache_dir / "10.9999_cached-doi.json"
    cache_file.write_text(json.dumps(cached_data), encoding="utf-8")
    
    # Fetch offline with custom cache directory
    res = fetch_crossref_work("10.9999/cached-doi", allow_network=False, cache_dir=cache_dir)
    assert res["status"] == "ok"
    assert res["message"]["title"] == ["Cached Metadata Title"]
