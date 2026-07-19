from __future__ import annotations


from integrity_agent.core.intake.batch_schema import LiteratureItem, BatchIntakeResult
from integrity_agent.workflows.batch_intake import _generate_summary_md


def test_generate_summary_md(tmp_path):
    summary_path = tmp_path / "summary.md"
    
    items = [
        # Retraction
        LiteratureItem(
            item_id="txt-L1",
            source_file="dois.txt",
            source_format="txt",
            doi="10.1000/retracted",
            normalized_doi="10.1000/retracted",
            title="Retracted Study",
            metadata_status="success",
            crossref_update_status="retraction"
        ),
        # EOC
        LiteratureItem(
            item_id="txt-L2",
            source_file="dois.txt",
            source_format="txt",
            doi="10.1000/eoc",
            normalized_doi="10.1000/eoc",
            title="EOC Study",
            metadata_status="success",
            crossref_update_status="expression_of_concern"
        ),
        # Correction
        LiteratureItem(
            item_id="txt-L3",
            source_file="dois.txt",
            source_format="txt",
            doi="10.1000/corrected",
            normalized_doi="10.1000/corrected",
            title="Corrected Study",
            metadata_status="success",
            crossref_update_status="correction"
        ),
        # Invalid
        LiteratureItem(
            item_id="txt-L4",
            source_file="dois.txt",
            source_format="txt",
            doi="invalid-doi",
            normalized_doi=None,
            metadata_status="failed",
            crossref_update_status="metadata_unavailable",
            warnings=["Invalid DOI format"]
        ),
        # Duplicate
        LiteratureItem(
            item_id="txt-L5",
            source_file="dois.txt",
            source_format="txt",
            doi="10.1000/retracted",
            normalized_doi="10.1000/retracted",
            title="Retracted Study",
            metadata_status="success",
            crossref_update_status="retraction",
            warnings=["Duplicate DOI in batch; using cached lookup."]
        ),
    ]
    
    result = BatchIntakeResult(
        source_file="dois.txt",
        source_format="txt",
        total_items=5,
        valid_dois=4,
        duplicate_dois=1,
        lookup_mode="offline",
        items=items
    )
    
    _generate_summary_md(summary_path, result)
    
    assert summary_path.exists()
    content = summary_path.read_text(encoding="utf-8")
    
    # 1. Assert headers/sections are present
    assert "# Batch Intake Summary Report" in content
    assert "## Batch input source" in content
    assert "## Number of items parsed" in content
    assert "## Number of valid DOIs" in content
    assert "## Number of duplicate DOIs" in content
    assert "## Metadata lookup mode: offline / allow-network" in content
    assert "## Retraction metadata summary" in content
    assert "## Correction / expression of concern summary" in content
    assert "## Items requiring manual verification" in content
    assert "## Limitations" in content
    assert "## Do-not-overclaim notice" in content
    
    # 2. Assert counts
    assert "Total parsed items: 5" in content
    assert "Valid DOIs: 4" in content
    assert "Duplicate DOIs: 1" in content
    assert "Retractions detected: 2" in content
    assert "Corrections detected: 1" in content
    assert "Expressions of concern detected: 1" in content
    
    # 3. Assert safety contract phrasing
    assert "does not determine misconduct" in content
    assert "no_known_update` does not prove the paper is reliable" in content
    assert "metadata_unavailable` does not imply that the paper is suspicious" in content
    assert "correction notice does not imply misconduct" in content
