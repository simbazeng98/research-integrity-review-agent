from __future__ import annotations

from integrity_agent.core.metadata.crossref_updates import parse_crossref_updates


def test_parse_crossref_updates_empty():
    res = parse_crossref_updates({})
    assert res.status == "metadata_unavailable"
    assert res.doi == "unknown"


def test_parse_crossref_updates_no_updates():
    work = {
        "message": {
            "DOI": "10.1000/xyz123",
            "title": ["Stable Article"],
        }
    }
    res = parse_crossref_updates(work)
    assert res.status == "no_known_update"
    assert res.doi == "10.1000/xyz123"
    assert len(res.updates) == 0


def test_parse_crossref_updates_retraction():
    work = {
        "message": {
            "DOI": "10.1000/retracted-art",
            "updated-by": [
                {
                    "type": "retraction",
                    "DOI": "10.1000/notice-doi",
                    "label": "Retraction notice",
                    "updated": {"date-parts": [[2025, 12, 31]]}
                }
            ]
        }
    }
    res = parse_crossref_updates(work)
    assert res.status == "retraction"
    assert len(res.updates) == 1
    assert res.updates[0].update_type == "retraction"
    assert res.updates[0].source == "updated-by"
    assert res.updates[0].label == "Retraction notice"
    assert res.updates[0].updated_date == "2025-12-31"
    assert res.updates[0].related_doi == "10.1000/notice-doi"


def test_parse_crossref_updates_reinstatement_overrides_retraction():
    work = {
        "message": {
            "DOI": "10.1000/reinstated-art",
            "updated-by": [
                {
                    "type": "retraction",
                    "DOI": "10.1000/notice-doi-1",
                    "label": "Retracted",
                    "updated": {"date-parts": [[2023, 1, 1]]}
                },
                {
                    "type": "reinstatement",
                    "DOI": "10.1000/notice-doi-2",
                    "label": "Reinstated",
                    "updated": {"date-parts": [[2023, 2, 1]]}
                }
            ]
        }
    }
    res = parse_crossref_updates(work)
    assert res.status == "reinstatement"
    assert len(res.updates) == 2


def test_parse_crossref_updates_correction():
    work = {
        "message": {
            "DOI": "10.1000/corrected-art",
            "updated-by": [
                {
                    "type": "correction",
                    "DOI": "10.1000/correction-notice",
                    "label": "Correction notice",
                    "updated": {"date-parts": [[2024, 6]]}
                }
            ]
        }
    }
    res = parse_crossref_updates(work)
    assert res.status == "correction"
    assert len(res.updates) == 1
    assert res.updates[0].updated_date == "2024-06"
