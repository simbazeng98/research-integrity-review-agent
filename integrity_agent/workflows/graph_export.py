from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from integrity_agent.core.path_display import display_path

def run_graph_export(
    unified_index_path: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path, Path]:
    index_path = Path(unified_index_path)
    if not index_path.exists():
        raise FileNotFoundError(f"Unified index path not found: {index_path}")

    if output_dir is None:
        out_path = Path("outputs") / "graph_export"
    else:
        out_path = Path(output_dir)

    out_path.mkdir(parents=True, exist_ok=True)

    nodes_file = out_path / "provenance_graph_nodes.jsonl"
    edges_file = out_path / "provenance_graph_edges.jsonl"
    summary_file = out_path / "provenance_graph_summary.md"

    # Set up data structures
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    # Read findings
    findings = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # Ingest package node
    pkg_id = "current_package"
    # Try to deduce package ID from index path or findings
    for f in findings:
        prov = f.get("provenance") or {}
        if isinstance(prov, dict) and prov.get("package_id"):
            pkg_id = prov["package_id"]
            break
    if pkg_id == "current_package":
        # Check parent folder name
        pkg_id = index_path.parent.name or "package"

    package_node_id = f"package:{pkg_id}"
    nodes[package_node_id] = {
        "node_id": package_node_id,
        "node_type": "package",
        "label": pkg_id,
        "metadata": {}
    }

    edge_counter = 1
    for f in findings:
        finding_id = f.get("finding_id") or "unknown_finding"
        rule_id = f.get("rule_id") or f.get("type") or "unknown_rule"

        # Source file resolution
        src = f.get("source_file")
        if not src:
            ev_list = f.get("evidence") or f.get("evidence_items") or []
            if ev_list and isinstance(ev_list[0], dict):
                src = ev_list[0].get("source") or ev_list[0].get("relative_path")
        if not src:
            src = "unknown_source"

        src_name = Path(src).name
        source_node_id = f"source:{src_name}"
        rule_node_id = f"rule:{rule_id}"
        finding_node_id = f"finding:{finding_id}"

        # 1. Source Node
        if source_node_id not in nodes:
            nodes[source_node_id] = {
                "node_id": source_node_id,
                "node_type": "source_file",
                "label": src_name,
                "metadata": {}
            }
            # package -> source edge
            edges.append({
                "edge_id": f"edge-{edge_counter}",
                "source": package_node_id,
                "target": source_node_id,
                "relation_type": "contains"
            })
            edge_counter += 1

        # 2. Rule Node
        if rule_node_id not in nodes:
            nodes[rule_node_id] = {
                "node_id": rule_node_id,
                "node_type": "rule",
                "label": rule_id,
                "metadata": {}
            }

        # 3. Finding Node
        if finding_node_id not in nodes:
            nodes[finding_node_id] = {
                "node_id": finding_node_id,
                "node_type": "finding",
                "label": finding_id,
                "metadata": {
                    "risk_level": f.get("risk_level") or f.get("risk") or "low",
                    "safe_report_language": f.get("safe_report_language") or f.get("summary") or ""
                }
            }
            # source -> finding edge
            edges.append({
                "edge_id": f"edge-{edge_counter}",
                "source": source_node_id,
                "target": finding_node_id,
                "relation_type": "triggered_in"
            })
            edge_counter += 1
            # rule -> finding edge
            edges.append({
                "edge_id": f"edge-{edge_counter}",
                "source": rule_node_id,
                "target": finding_node_id,
                "relation_type": "defined"
            })
            edge_counter += 1

        # 4. Verification Question Nodes
        mv_val = f.get("manual_verification")
        requests = []
        if isinstance(mv_val, dict):
            requests = mv_val.get("requests") or []
        elif isinstance(mv_val, list):
            requests = mv_val

        for idx, q_text in enumerate(requests, start=1):
            q_id = f"question:{finding_id}-q{idx}"
            if q_id not in nodes:
                nodes[q_id] = {
                    "node_id": q_id,
                    "node_type": "verification_question",
                    "label": q_text[:60] + "..." if len(q_text) > 60 else q_text,
                    "metadata": {
                        "full_text": q_text
                    }
                }
                # finding -> question edge
                edges.append({
                    "edge_id": f"edge-{edge_counter}",
                    "source": finding_node_id,
                    "target": q_id,
                    "relation_type": "verified_by"
                })
                edge_counter += 1

    # Write nodes JSONL
    with nodes_file.open("w", encoding="utf-8") as f:
        for node in nodes.values():
            f.write(json.dumps(node, ensure_ascii=False) + "\n")

    # Write edges JSONL
    with edges_file.open("w", encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")

    # Generate Markdown summary
    summary_lines = [
        "# Provenance Graph Export Summary",
        "",
        "> [!NOTE]",
        "> This provenance graph lists integrity signals and evidence chains for human review. It does not perform cross-paper mills inference or draw misconduct conclusions.",
        "",
        "## Graph Statistics",
        f"- **Total Nodes**: {len(nodes)}",
        f"- **Total Edges**: {len(edges)}",
        "",
        "### Node Counts by Type",
    ]

    counts: dict[str, int] = {}
    for node in nodes.values():
        counts[node["node_type"]] = counts.get(node["node_type"], 0) + 1

    for k, v in counts.items():
        summary_lines.append(f"- `{k}` nodes: {v}")

    summary_lines.extend([
        "",
        "## Summary of Exported Nodes",
        ""
    ])

    for n_type in sorted(counts.keys()):
        summary_lines.append(f"### {n_type.capitalize()} Nodes")
        for node in nodes.values():
            if node["node_type"] == n_type:
                summary_lines.append(f"- `{node['node_id']}`: {node['label']}")
        summary_lines.append("")

    summary_file.write_text("\n".join(summary_lines).strip() + "\n", encoding="utf-8")

    print(f"Wrote provenance graph nodes: {display_path(nodes_file)}")
    print(f"Wrote provenance graph edges: {display_path(edges_file)}")
    print(f"Wrote provenance graph summary: {display_path(summary_file)}")

    return nodes_file, edges_file, summary_file
