from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

from integrity_agent.workflows.graph_export import run_graph_export

def test_graph_export_workflow(tmp_path):
    # 1. Create a dummy unified index
    index_file = tmp_path / "unified_evidence_index.jsonl"
    finding = {
        "finding_id": "PV-RULESET-FIND-001",
        "finding_category": "pv_evidence_completeness",
        "rule_id": "pv_jv_mask_area_completeness",
        "risk_level": "low",
        "evidence": [{"source": "toy_pv.csv", "location": "Table tbl-1"}],
        "manual_verification": {"needed": True, "requests": ["Is the aperture mask area reported?"]},
        "safe_report_language": "Candidate device mask area completeness gap.",
        "provenance": {
            "package_id": "my_test_package",
            "missing_fields": ["mask_area"]
        }
    }
    with index_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(finding) + "\n")

    # 2. Run graph export
    out_dir = tmp_path / "outputs"
    nodes_file, edges_file, summary_file = run_graph_export(index_file, output_dir=out_dir)

    assert nodes_file.exists()
    assert edges_file.exists()
    assert summary_file.exists()

    # Load nodes
    nodes = []
    with nodes_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                nodes.append(json.loads(line))

    # Load edges
    edges = []
    with edges_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                edges.append(json.loads(line))

    # Check node types
    node_types = {n["node_type"] for n in nodes}
    assert "package" in node_types
    assert "source_file" in node_types
    assert "rule" in node_types
    assert "finding" in node_types
    assert "verification_question" in node_types

    package_node = next(n for n in nodes if n["node_type"] == "package")
    assert package_node["label"] == "my_test_package"

    # Check edges
    assert len(edges) > 0
    relations = {e["relation_type"] for e in edges}
    assert "contains" in relations
    assert "triggered_in" in relations
    assert "defined" in relations
    assert "verified_by" in relations

    # Check path safety
    summary_text = summary_file.read_text(encoding="utf-8").lower()
    for pattern in ["file:///", "d:/", "c:/", "d:\\", "c:\\"]:
        assert pattern not in summary_text


def test_graph_export_cli(tmp_path):
    index_file = tmp_path / "unified_evidence_index.jsonl"
    finding = {
        "finding_id": "PV-RULESET-FIND-001",
        "finding_category": "pv_evidence_completeness",
        "rule_id": "pv_jv_mask_area_completeness",
        "risk_level": "low",
        "evidence": [{"source": "toy_pv.csv", "location": "Table tbl-1"}],
        "manual_verification": {"needed": True, "requests": ["Q1"]},
        "safe_report_language": "Candidate completeness gap."
    }
    with index_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(finding) + "\n")

    out_dir = tmp_path / "outputs"
    result = subprocess.run(
        [sys.executable, "-m", "integrity_agent", "graph-export", str(index_file), "-o", str(out_dir)],
        text=True,
        capture_output=True,
        check=True
    )
    assert result.returncode == 0
    assert (out_dir / "provenance_graph_nodes.jsonl").exists()
    assert (out_dir / "provenance_graph_edges.jsonl").exists()
    assert (out_dir / "provenance_graph_summary.md").exists()
