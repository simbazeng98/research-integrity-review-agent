import re
import subprocess
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Metadata and source status",
    "Detected risk signals",
    "Evidence locations",
    "Alternative benign explanations",
    "Missing verification materials",
    "Suggested verification questions",
    "Limitations",
    "Do-not-overclaim notice",
]

FORBIDDEN_PHRASES = [
    "fraud confirmed",
    "misconduct confirmed",
    "造假成立",
    "学术不端成立",
    "作者造假",
]


def test_reader_review_report_cli_writes_required_sections():
    project_root = Path(__file__).resolve().parents[1]
    findings_path = project_root / "outputs" / "rule_findings.jsonl"
    report_path = project_root / "outputs" / "reader_review_report.md"
    metadata_json_path = project_root / "outputs" / "paper_case" / "metadata.json"
    
    if report_path.exists():
        report_path.unlink()
    if metadata_json_path.exists():
        metadata_json_path.unlink()

    # Temporarily hide image/table findings so they don't pollute the snapshot report
    img_findings = project_root / "outputs" / "image_intake" / "image_findings.jsonl"
    img_sim = project_root / "outputs" / "image_intake" / "image_similarity_candidates.jsonl"
    tbl_findings = project_root / "outputs" / "table_intake" / "table_numeric_findings.jsonl"
    pv_findings = project_root / "outputs" / "pv_domain" / "pv_findings.jsonl"
    raw_pv_findings = project_root / "outputs" / "raw_pv" / "raw_pv_findings.jsonl"
    
    img_findings_bak = project_root / "outputs" / "image_intake" / "image_findings.jsonl.bak"
    img_sim_bak = project_root / "outputs" / "image_intake" / "image_similarity_candidates.jsonl.bak"
    tbl_findings_bak = project_root / "outputs" / "table_intake" / "table_numeric_findings.jsonl.bak"
    pv_findings_bak = project_root / "outputs" / "pv_domain" / "pv_findings.jsonl.bak"
    raw_pv_findings_bak = project_root / "outputs" / "raw_pv" / "raw_pv_findings.jsonl.bak"

    if img_findings.exists():
        img_findings.rename(img_findings_bak)
    if img_sim.exists():
        img_sim.rename(img_sim_bak)
    if tbl_findings.exists():
        tbl_findings.rename(tbl_findings_bak)
    if pv_findings.exists():
        pv_findings.rename(pv_findings_bak)
    if raw_pv_findings.exists():
        raw_pv_findings.rename(raw_pv_findings_bak)

    try:
        # Generate findings
        subprocess.run(
            [
                sys.executable,
                "-m",
                "integrity_agent",
                "run-rules",
                "examples/toy_rule_package",
            ],
            check=True,
            cwd=project_root,
            text=True,
            capture_output=True,
        )

        # Generate report
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "integrity_agent",
                "report-reader-review",
                str(findings_path),
            ],
            check=False,
            cwd=project_root,
            text=True,
            capture_output=True,
        )

        assert result.returncode == 0, result.stderr
        report = report_path.read_text(encoding="utf-8")

        # 1. Assert all required sections are present
        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in report

        # 2. Assert NO forbidden overclaiming phrases are present
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in report.lower(), f"Report contains forbidden overclaiming language: '{phrase}'"

        # 3. Assert additional formatting sanity checks
        assert "\n- - " not in report
        assert "does not determine misconduct" in report
        assert "numeric_fixed_delta_between_columns" in report

        # 4. Compare with the expected snapshot
        snapshot_path = project_root / "tests" / "snapshots" / "reader_review_report_expected.md"
        expected = snapshot_path.read_text(encoding="utf-8")

        # Normalize findings source line which is system-dependent
        normalized_report = re.sub(
            r"- Findings source: `.*`$",
            r"- Findings source: `<PROJECT_ROOT>/outputs/rule_findings.jsonl`",
            report,
            flags=re.MULTILINE
        )

        # Normalize newlines for cross-platform comparison
        normalized_report = normalized_report.replace("\r\n", "\n")
        expected = expected.replace("\r\n", "\n")

        assert normalized_report == expected
    finally:
        # Restore hidden files
        if img_findings_bak.exists():
            img_findings_bak.rename(img_findings)
        if img_sim_bak.exists():
            img_sim_bak.rename(img_sim)
        if tbl_findings_bak.exists():
            tbl_findings_bak.rename(tbl_findings)
        if pv_findings_bak.exists():
            pv_findings_bak.rename(pv_findings)
        if raw_pv_findings_bak.exists():
            raw_pv_findings_bak.rename(raw_pv_findings)


def test_reader_review_report_with_metadata_json(tmp_path):
    # Setup test by mocking files and environment
    from integrity_agent.workflows.report_reader_review import write_reader_review_report
    import json
    
    project_root = Path(__file__).resolve().parents[1]
    
    # 1. Create a dummy metadata.json
    meta_dir = Path("outputs") / "paper_case"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_json_path = meta_dir / "metadata.json"
    
    dummy_meta = {
        "normalized_doi": "10.9999/dummy-doi",
        "status": "correction",
        "source_strength": "crossref_metadata",
        "title": "A Very Correction-Worthy Paper",
        "publisher": "Acme Publishing Group",
    }
    meta_json_path.write_text(json.dumps(dummy_meta), encoding="utf-8")
    
    try:
        # Create dummy findings.jsonl in tmp_path
        findings_jsonl = tmp_path / "findings.jsonl"
        findings_jsonl.write_text("", encoding="utf-8") # Empty is fine
        
        report_md = tmp_path / "report.md"
        write_reader_review_report(findings_jsonl, report_md)
        
        report_content = report_md.read_text(encoding="utf-8")
        
        # Verify metadata is integrated
        assert "Target DOI: `10.9999/dummy-doi`" in report_content
        assert "status: `correction`" in report_content
        assert "Title: A Very Correction-Worthy Paper" in report_content
        assert "Publisher: Acme Publishing Group" in report_content
    finally:
        # Cleanup metadata.json to not pollute subsequent tests
        if meta_json_path.exists():
            meta_json_path.unlink()

