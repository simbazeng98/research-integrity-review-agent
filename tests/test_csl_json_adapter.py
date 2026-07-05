from __future__ import annotations

import json
import pytest
from pathlib import Path

from integrity_agent.core.intake.adapters.csl_json import parse_csl_json


def test_parse_csl_json_valid(tmp_path):
    csl_file = tmp_path / "zotero.json"
    csl_data = [
        {
            "id": "item-1",
            "type": "article-journal",
            "title": "Macro-molecular Superconductivity",
            "container-title": "Journal of Superconductivity",
            "DOI": "10.1000/xyz123",
            "issued": {
                "date-parts": [[2025, 6, 15]]
            }
        },
        {
            "id": "item-2",
            "type": "article-journal",
            "title": "A Second Paper",
            "DOI": "invalid-doi",
            "issued": {
                "raw": "2024"
            }
        },
        {
            "id": "item-3",
            "title": "A Third Paper",
            "issued": "2023"
        }
    ]
    csl_file.write_text(json.dumps(csl_data), encoding="utf-8")
    
    items = parse_csl_json(csl_file)
    
    assert len(items) == 3
    
    # Item 1
    assert items[0].item_id == "item-1"
    assert items[0].title == "Macro-molecular Superconductivity"
    assert items[0].journal == "Journal of Superconductivity"
    assert items[0].doi == "10.1000/xyz123"
    assert items[0].normalized_doi == "10.1000/xyz123"
    assert items[0].year == "2025"
    assert len(items[0].warnings) == 0
    
    # Item 2
    assert items[1].item_id == "item-2"
    assert items[1].doi == "invalid-doi"
    assert items[1].normalized_doi is None
    assert items[1].year == "2024"
    assert len(items[1].warnings) == 1
    
    # Item 3
    assert items[2].item_id == "item-3"
    assert items[2].doi is None
    assert items[2].normalized_doi is None
    assert items[2].year == "2023"
    assert len(items[2].warnings) == 1
    assert "Missing DOI" in items[2].warnings[0]
