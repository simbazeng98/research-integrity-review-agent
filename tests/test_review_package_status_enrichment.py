from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from integrity_agent.workflows.validate_ledger import validate_ledger_file


def test_review_package_status_enrichment_integration(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "outputs"

    # Run review-package on toy package
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            "examples/toy_review_package",
            "-o",
            str(output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    # Verify status-enrich output directory files are copied
    se_jsonl = output_dir / "status_enrich" / "status_items.jsonl"
    se_summary = output_dir / "status_enrich" / "status_summary.md"
    assert se_jsonl.exists()
    assert se_summary.exists()

    # Validate status_items.jsonl using validate-ledger
    validation_result = validate_ledger_file(se_jsonl)
    assert validation_result.ok is True
    assert validation_result.records > 0

    # Read unified_evidence_index.jsonl
    index_jsonl = output_dir / "unified_evidence_index.jsonl"
    assert index_jsonl.exists()

    findings = []
    with open(index_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # Find the status enrichment record
    status_findings = [f for f in findings if f.get("finding_category") == "status_enrichment"]
    assert len(status_findings) == 1

    sf = status_findings[0]
    assert sf["provenance"]["doi"] == "10.1002/adma.202000000"
    assert sf["provenance"]["raw_status"] == "correction"
    assert sf["risk"] == "low"
    assert sf["risk_level"] == "low"

    # Verify relation details
    status_relations = sf["provenance"]["status_relations"]
    assert len(status_relations) == 1
    rel = status_relations[0]
    assert rel["doi"] == "10.1002/adma.202000000-corr"
    assert rel["type"] == "correction"
    assert rel["date"] == "2024-05-01"
    assert rel["relation"] == "updated-by"

    # Verify evidence metadata details
    assert "evidence" in sf
    ev = sf["evidence"][0]
    assert ev["metadata"]["updates_count"] == 1
    assert ev["metadata"]["updates"][0]["doi"] == "10.1002/adma.202000000-corr"

    # Verify summary md exists and contains safety notice and dashboard link
    summary_md = output_dir / "review_package_summary.md"
    assert summary_md.exists()
    summary_content = summary_md.read_text(encoding="utf-8")
    assert "Interactive Review Dashboard" in summary_content
    # Since status_enrich is low risk correction, it should be listed in the report
    assert "Publication Status Enrichment:" in summary_content or "status_enrichment" in summary_content


def test_review_package_status_enrichment_no_bleed(tmp_path):
    project_root = Path(__file__).resolve().parents[1]

    # 1. Use the SAME output directory for both runs
    shared_output_dir = tmp_path / "same_output_dir"

    # Run package with DOI first to populate status enrichment
    result_doi = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            "examples/toy_review_package",
            "-o",
            str(shared_output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result_doi.returncode == 0, result_doi.stderr

    # Verify DOI package run contains status enrichment
    index_doi = shared_output_dir / "unified_evidence_index.jsonl"
    assert index_doi.exists()

    se_jsonl_doi = shared_output_dir / "status_enrich" / "status_items.jsonl"
    se_summary_doi = shared_output_dir / "status_enrich" / "status_summary.md"
    assert se_jsonl_doi.exists()
    assert se_summary_doi.exists()

    findings_doi = []
    with open(index_doi, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings_doi.append(json.loads(line))
    status_findings_doi = [f for f in findings_doi if f.get("finding_category") == "status_enrichment"]
    assert len(status_findings_doi) == 1

    # 2. Create a copy of the toy package and remove metadata/doi.txt
    toy_pkg_src = project_root / "examples/toy_review_package"
    pkg_no_doi = tmp_path / "toy_review_package_no_doi"
    pkg_no_doi.mkdir()
    # Copy relevant folders/files
    import shutil
    shutil.copytree(toy_pkg_src / "images", pkg_no_doi / "images")
    shutil.copytree(toy_pkg_src / "tables", pkg_no_doi / "tables")
    shutil.copytree(toy_pkg_src / "pv", pkg_no_doi / "pv")
    shutil.copytree(toy_pkg_src / "raw_pv", pkg_no_doi / "raw_pv")

    # Create empty metadata directory
    (pkg_no_doi / "metadata").mkdir()

    # 3. Run review-package on the package without DOI using the SAME output directory
    result_nodoi = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            str(pkg_no_doi),
            "-o",
            str(shared_output_dir),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result_nodoi.returncode == 0, result_nodoi.stderr

    # Verify no-DOI package run DOES NOT contain status enrichment (stale bleed fix verification)
    index_nodoi = shared_output_dir / "unified_evidence_index.jsonl"
    assert index_nodoi.exists()
    findings_nodoi = []
    with open(index_nodoi, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings_nodoi.append(json.loads(line))
    status_findings_nodoi = [f for f in findings_nodoi if f.get("finding_category") == "status_enrichment"]
    assert len(status_findings_nodoi) == 0

    # Verify that status_enrich subdirectory and files under shared_output_dir DO NOT exist anymore
    se_jsonl_nodoi = shared_output_dir / "status_enrich" / "status_items.jsonl"
    se_summary_nodoi = shared_output_dir / "status_enrich" / "status_summary.md"
    assert not se_jsonl_nodoi.exists()
    assert not se_summary_nodoi.exists()
    assert not (shared_output_dir / "status_enrich").exists()


def test_status_enrichment_dashboard_rendering(tmp_path):
    project_root = Path(__file__).resolve().parents[1]

    # 1. Run for toy package (with DOI)
    output_dir_doi = tmp_path / "outputs_doi"
    result_doi = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            "examples/toy_review_package",
            "-o",
            str(output_dir_doi),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result_doi.returncode == 0, result_doi.stderr

    dashboard_doi = output_dir_doi / "review_package_dashboard.html"
    assert dashboard_doi.exists()
    html_content_doi = dashboard_doi.read_text(encoding="utf-8")

    # Assertions for toy package with status enrichment card
    assert "Publication Status / Status Enrichment" in html_content_doi
    assert "文献出版状态 / 状态富集" in html_content_doi
    assert "10.1002/adma.202000000" in html_content_doi
    assert "10.1002/adma.202000000-corr" in html_content_doi
    assert "not proof of research misconduct" in html_content_doi
    assert "并非学术不端的证据" in html_content_doi

    # 2. Run for no-DOI package
    toy_pkg_src = project_root / "examples/toy_review_package"
    pkg_no_doi = tmp_path / "toy_review_package_no_doi"
    pkg_no_doi.mkdir()

    import shutil
    shutil.copytree(toy_pkg_src / "images", pkg_no_doi / "images")
    shutil.copytree(toy_pkg_src / "tables", pkg_no_doi / "tables")
    shutil.copytree(toy_pkg_src / "pv", pkg_no_doi / "pv")
    shutil.copytree(toy_pkg_src / "raw_pv", pkg_no_doi / "raw_pv")
    (pkg_no_doi / "metadata").mkdir()

    output_dir_nodoi = tmp_path / "outputs_nodoi"
    result_nodoi = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "review-package",
            str(pkg_no_doi),
            "-o",
            str(output_dir_nodoi),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result_nodoi.returncode == 0, result_nodoi.stderr

    dashboard_nodoi = output_dir_nodoi / "review_package_dashboard.html"
    assert dashboard_nodoi.exists()
    html_content_nodoi = dashboard_nodoi.read_text(encoding="utf-8")

    # Assertions for no-DOI package where status card should NOT appear
    assert "Publication Status / Status Enrichment" not in html_content_nodoi
    assert "文献出版状态 / 状态富集" not in html_content_nodoi
    assert "status-enrichment-card" not in html_content_nodoi


def test_render_dashboard_html_generator():
    from integrity_agent.core.reporting.html_dashboard import render_dashboard_html

    # Create a generator containing a status_enrichment dict
    def gen_findings():
        yield {
            "finding_id": "status_enrich_10_9999_test",
            "finding_category": "status_enrichment",
            "type": "status_enrichment",
            "title": {"en": "Publication Status Enrichment: 10.9999/test", "zh": "文献状态富集: 10.9999/test"},
            "summary": {"en": "Publication status for DOI 10.9999/test enriched to 'retraction' based on Crossref.", "zh": "文献 DOI 10.9999/test 状态为 'retraction'。"},
            "risk": "high",
            "risk_level": "high",
            "needs_manual_review": True,
            "evidence": [],
            "provenance": {
                "doi": "10.9999/test",
                "raw_status": "retraction",
                "status_relations": []
            }
        }

    html_out = render_dashboard_html(gen_findings())

    # Assertions
    assert "Publication Status / Status Enrichment" in html_out
    assert "10.9999/test" in html_out
    assert "not proof of research misconduct" in html_out
