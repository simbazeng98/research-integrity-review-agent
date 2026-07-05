from __future__ import annotations

import pytest
from pathlib import Path

from integrity_agent.core.intake.adapters.ris_basic import parse_ris


def test_parse_ris_valid(tmp_path):
    ris_file = tmp_path / "refs.ris"
    ris_file.write_text(
        """
TY  - JOUR
TI  - Room Temperature Superconductivity Myth
AU  - Smith, J.
AU  - Doe, A.
JO  - Journal of Anomalous Results
PY  - 2026/07/04/
DO  - 10.0000/toy-retracted
UR  - https://example.com
ER  - 

TY  - CONF
T1  - A Second Conference Paper
AU  - Jones, B.
T2  - Proceedings of Superconductivity
Y1  - 2025
DO  - invalid-doi
ER  - 

TY  - BOOK
T1  - Book without DOI
ER  - 
""",
        encoding="utf-8"
    )
    
    items = parse_ris(ris_file)
    
    assert len(items) == 3
    
    # Entry 1: Journal Article
    assert items[0].item_id == "ris-R1"
    assert items[0].reference_type == "JOUR"
    assert items[0].title == "Room Temperature Superconductivity Myth"
    assert items[0].authors == ["Smith, J.", "Doe, A."]
    assert items[0].journal == "Journal of Anomalous Results"
    assert items[0].year == "2026"
    assert items[0].doi == "10.0000/toy-retracted"
    assert items[0].normalized_doi == "10.0000/toy-retracted"
    assert "UR" in items[0].raw_tags
    assert items[0].raw_tags["UR"] == ["https://example.com"]
    assert len(items[0].warnings) == 0
    
    # Entry 2: Conference Paper with invalid DOI
    assert items[1].item_id == "ris-R2"
    assert items[1].reference_type == "CONF"
    assert items[1].title == "A Second Conference Paper"
    assert items[1].authors == ["Jones, B."]
    assert items[1].journal == "Proceedings of Superconductivity"
    assert items[1].year == "2025"
    assert items[1].doi == "invalid-doi"
    assert items[1].normalized_doi is None
    assert len(items[1].warnings) == 1
    
    # Entry 3: Book without DOI
    assert items[2].item_id == "ris-R3"
    assert items[2].reference_type == "BOOK"
    assert items[2].title == "Book without DOI"
    assert items[2].doi is None
    assert items[2].normalized_doi is None
    assert len(items[2].warnings) == 1
    assert "Missing DOI" in items[2].warnings[0]
