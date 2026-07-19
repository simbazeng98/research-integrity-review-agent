from __future__ import annotations

import urllib.error
import pytest

from integrity_agent.core.metadata.crossref_updates import parse_crossref_updates
from integrity_agent.core.metadata.crossref_client import fetch_crossref_work, CrossrefRateLimitError


def test_crossref_update_parser_deduplication():
    # Mock data with duplicate retraction notice DOIs
    work = {
        "message": {
            "DOI": "10.1000/main-art",
            "updated-by": [
                {
                    "type": "retraction",
                    "DOI": "10.1000/notice-dup",
                    "label": "Notice Dup",
                    "updated": {"date-parts": [[2025, 1, 1]]}
                },
                {
                    "type": "retraction",
                    "DOI": "10.1000/notice-dup", # Duplicate DOI
                    "label": "Notice Dup Duplicate",
                    "updated": {"date-parts": [[2025, 1, 1]]}
                },
                {
                    "type": "correction",
                    "DOI": "10.1000/notice-other",
                    "label": "Correction Notice",
                    "updated": {"date-parts": [[2025, 2, 1]]}
                }
            ]
        }
    }
    
    parsed = parse_crossref_updates(work)
    
    assert parsed.status == "retraction"
    # Should only contain 2 updates (1 unique retraction and 1 correction)
    assert len(parsed.updates) == 2
    
    # Check that both updates have correct type
    update_types = {u.update_type for u in parsed.updates}
    assert update_types == {"retraction", "correction"}


def test_crossref_client_429_retry_after(monkeypatch):
    # Mock urllib.request.urlopen to raise HTTPError with code 429
    def mock_urlopen(*args, **kwargs):
        # Create a mock HTTPError
        headers = {"Retry-After": "120"}
        exception = urllib.error.HTTPError(
            url="https://api.crossref.org/works/10.1000/xyz",
            code=429,
            msg="Too Many Requests",
            hdrs=headers, # type: ignore
            fp=None
        )
        raise exception

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    with pytest.raises(CrossrefRateLimitError, match="Retry-After: 120 seconds"):
        fetch_crossref_work("10.1000/xyz", allow_network=True)


def test_batch_intake_deduplication(tmp_path):
    from integrity_agent.workflows.batch_intake import run_batch_intake
    
    txt_file = tmp_path / "dois.txt"
    txt_file.write_text(
        "\n".join([
            "10.0000/toy-retracted",
            "10.0000/toy-retracted", # Duplicate
        ]),
        encoding="utf-8"
    )
    
    jsonl, csv, summary = run_batch_intake(
        txt_file,
        allow_network=False,
        output_dir=tmp_path
    )
    
    import json
    records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    
    assert len(records) == 2
    assert records[0]["doi"] == "10.0000/toy-retracted"
    assert records[1]["doi"] == "10.0000/toy-retracted"
    
    # Duplicate item should copy status and contain warning
    assert records[1]["crossref_update_status"] == "retraction"
    assert any("Duplicate DOI" in w for w in records[1]["warnings"])

