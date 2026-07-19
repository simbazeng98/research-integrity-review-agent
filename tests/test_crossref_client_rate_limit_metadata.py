from __future__ import annotations

import json
import urllib.error
import urllib.request
import pytest

from integrity_agent.core.metadata.crossref_client import fetch_crossref_work, CrossrefRateLimitError


def test_cache_hit_flag_and_mock(tmp_path):
    # Mock fixture
    data = fetch_crossref_work("10.0000/toy-retracted", allow_network=False, cache_dir=tmp_path)
    assert data["_cache_hit"] is False

    # Mock writing a file to cache to check cache hit
    cache_file = tmp_path / "10.0000_toy-retracted.json"
    cache_file.write_text(json.dumps({"DOI": "10.0000/toy-retracted", "title": ["Mock Title"]}), encoding="utf-8")

    data_cached = fetch_crossref_work("10.0000/toy-retracted", allow_network=False, cache_dir=tmp_path)
    assert data_cached["_cache_hit"] is True


def test_rate_limit_headers_in_response(monkeypatch, tmp_path):
    class MockResponse:
        def __init__(self):
            self.headers = {
                "x-rate-limit-limit": "50",
                "x-rate-limit-interval": "1s"
            }
        def read(self):
            return json.dumps({"message": {"DOI": "10.1000/some-doi"}}).encode("utf-8")
        def decode(self, *args, **kwargs):
            return self.read().decode(*args, **kwargs)
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, **kwargs):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # Trigger request
    data = fetch_crossref_work("10.1000/some-doi", allow_network=True, cache_dir=tmp_path)
    assert data["_cache_hit"] is False
    assert data["_x_rate_limit_limit"] == "50"
    assert data["_x_rate_limit_interval"] == "1s"


def test_rate_limit_error_with_limits(monkeypatch, tmp_path):
    def mock_urlopen_raise(req, **kwargs):
        headers = {
            "Retry-After": "60",
            "x-rate-limit-limit": "100",
            "x-rate-limit-interval": "15m"
        }
        exception = urllib.error.HTTPError(
            url="https://api.crossref.org/works/10.1000/xyz",
            code=429,
            msg="Too Many Requests",
            hdrs=headers, # type: ignore
            fp=None
        )
        raise exception

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_raise)

    with pytest.raises(CrossrefRateLimitError) as excinfo:
        fetch_crossref_work("10.1000/xyz", allow_network=True, cache_dir=tmp_path)
    
    msg = str(excinfo.value)
    assert "Retry-After: 60 seconds" in msg
    assert "Limit: 100" in msg
    assert "Interval: 15m" in msg
