from __future__ import annotations


from integrity_agent.core.intake.adapters.bibtex_basic import parse_bibtex


def test_parse_bibtex_valid(tmp_path):
    bib_file = tmp_path / "refs.bib"
    bib_file.write_text(
        """
@article{cite1,
  author = {Smith, John},
  title = {Superconductivity at Room Temperature},
  journal = {Physical Review Letters},
  year = 2026,
  doi = {10.1000/xyz123}
}

@inproceedings{cite2,
  title = "Another paper on Superconductivity",
  booktitle = {Proceedings of the ACM},
  year = {2025},
  doi = "invalid-doi-prefix"
}

@book{cite3,
  title = {Superconductivity Handbook},
  year = 2024
}
""",
        encoding="utf-8"
    )
    
    items = parse_bibtex(bib_file)
    
    assert len(items) == 3
    
    # Item 1
    assert items[0].item_id == "cite1"
    assert items[0].title == "Superconductivity at Room Temperature"
    assert items[0].journal == "Physical Review Letters"
    assert items[0].doi == "10.1000/xyz123"
    assert items[0].normalized_doi == "10.1000/xyz123"
    assert items[0].year == "2026"
    assert len(items[0].warnings) == 0
    
    # Item 2
    assert items[1].item_id == "cite2"
    assert items[1].title == "Another paper on Superconductivity"
    assert items[1].journal == "Proceedings of the ACM"
    assert items[1].doi == "invalid-doi-prefix"
    assert items[1].normalized_doi is None
    assert items[1].year == "2025"
    assert len(items[1].warnings) == 1
    
    # Item 3
    assert items[2].item_id == "cite3"
    assert items[2].title == "Superconductivity Handbook"
    assert items[2].doi is None
    assert items[2].normalized_doi is None
    assert items[2].year == "2024"
    assert len(items[2].warnings) == 1
    assert "Missing DOI" in items[2].warnings[0]
