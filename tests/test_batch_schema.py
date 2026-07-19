from __future__ import annotations

from integrity_agent.core.intake.batch_schema import LiteratureItem, BatchIntakeResult


def test_literature_item_defaults():
    item = LiteratureItem(
        item_id="1",
        source_file="test.txt",
        source_format="txt",
        doi="10.1000/xyz"
    )
    assert item.normalized_doi is None
    assert item.metadata_status == "offline"
    assert item.crossref_update_status == "metadata_unavailable"
    assert item.warnings == []


def test_literature_item_to_dict():
    item = LiteratureItem(
        item_id="item-001",
        source_file="test.txt",
        source_format="txt",
        doi="10.1000/xyz",
        normalized_doi="10.1000/xyz",
        title="Test Title",
        year="2023",
        journal="Test Journal",
        metadata_status="success",
        crossref_update_status="no_known_update",
        warnings=["warning 1"]
    )
    d = item.to_dict()
    assert d["item_id"] == "item-001"
    assert d["title"] == "Test Title"
    assert d["warnings"] == ["warning 1"]


def test_batch_intake_result_to_dict():
    item = LiteratureItem(
        item_id="1",
        source_file="test.txt",
        source_format="txt",
        doi="10.1000/xyz",
        normalized_doi="10.1000/xyz"
    )
    res = BatchIntakeResult(
        source_file="test.txt",
        source_format="txt",
        total_items=1,
        valid_dois=1,
        duplicate_dois=0,
        lookup_mode="offline",
        items=[item]
    )
    d = res.to_dict()
    assert d["total_items"] == 1
    assert len(d["items"]) == 1
    assert d["items"][0]["item_id"] == "1"
