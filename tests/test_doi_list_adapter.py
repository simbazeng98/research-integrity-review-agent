from __future__ import annotations

import csv
import pytest
from pathlib import Path

from integrity_agent.core.intake.adapters.doi_list import parse_doi_list


def test_parse_doi_list_txt(tmp_path):
    txt_file = tmp_path / "dois.txt"
    txt_file.write_text(
        "\n".join([
            "10.1000/xyz123",
            "  ",
            "https://doi.org/10.1000/abc456",
            "invalid-doi-here",
            "10.1000/valid-ends-dot."
        ]),
        encoding="utf-8"
    )
    
    items = parse_doi_list(txt_file)
    
    assert len(items) == 4
    
    # Item 1: standard
    assert items[0].item_id == "txt-L1"
    assert items[0].doi == "10.1000/xyz123"
    assert items[0].normalized_doi == "10.1000/xyz123"
    assert len(items[0].warnings) == 0
    
    # Item 2: URL
    assert items[1].doi == "https://doi.org/10.1000/abc456"
    assert items[1].normalized_doi == "10.1000/abc456"
    assert len(items[1].warnings) == 0
    
    # Item 3: invalid
    assert items[2].doi == "invalid-doi-here"
    assert items[2].normalized_doi is None
    assert len(items[2].warnings) == 1
    assert "Invalid DOI format" in items[2].warnings[0]


def test_parse_doi_list_csv(tmp_path):
    csv_file = tmp_path / "dois.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "DOI", "year", "journal"])
        writer.writerow(["Paper A", "10.1000/xyz", "2020", "Nature"])
        writer.writerow(["Paper B", "invalid-doi", "2021", "Science"])
        writer.writerow(["Paper C", "", "2022", "Cell"]) # Empty DOI, skipped or added with missing status? (Empty lines are skipped by raw.strip() check)
        
    items = parse_doi_list(csv_file)
    
    assert len(items) == 2
    
    assert items[0].item_id == "csv-R1"
    assert items[0].doi == "10.1000/xyz"
    assert items[0].normalized_doi == "10.1000/xyz"
    assert items[0].title == "Paper A"
    assert items[0].year == "2020"
    assert items[0].journal == "Nature"
    assert len(items[0].warnings) == 0
    
    assert items[1].doi == "invalid-doi"
    assert items[1].normalized_doi is None
    assert len(items[1].warnings) == 1
