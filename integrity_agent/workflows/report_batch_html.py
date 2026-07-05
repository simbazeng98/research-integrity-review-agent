from __future__ import annotations

import html
import json
from pathlib import Path

DEFAULT_OUTPUT_HTML = Path("outputs") / "batch_intake" / "batch_review_table.html"


def generate_batch_html(
    jsonl_path: Path | str,
    output_path: Path | str | None = None,
) -> Path:
    """Read a JSONL batch intake file and render a static HTML review dashboard."""
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Batch file not found: {jsonl_path}")

    if output_path is None:
        resolved_out = DEFAULT_OUTPUT_HTML
    else:
        resolved_out = Path(output_path)

    resolved_out.parent.mkdir(parents=True, exist_ok=True)

    items = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    # HTML building block template
    html_lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "    <title>Metadata Review Batch Table</title>",
        "    <style>",
        "        :root {",
        "            --bg-color: #0f172a;",
        "            --text-color: #f1f5f9;",
        "            --card-bg: #1e293b;",
        "            --border-color: #334155;",
        "            --accent-color: #38bdf8;",
        "            --success-color: #10b981;",
        "            --warning-color: #f59e0b;",
        "            --danger-color: #ef4444;",
        "            --muted-color: #94a3b8;",
        "        }",
        "        body {",
        '            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        "            background-color: var(--bg-color);",
        "            color: var(--text-color);",
        "            margin: 0;",
        "            padding: 2rem;",
        "            line-height: 1.5;",
        "        }",
        "        .container {",
        "            max-width: 1500px;",
        "            margin: 0 auto;",
        "        }",
        "        header {",
        "            margin-bottom: 2rem;",
        "            border-bottom: 1px solid var(--border-color);",
        "            padding-bottom: 1.5rem;",
        "        }",
        "        h1 {",
        "            font-size: 1.8rem;",
        "            font-weight: 700;",
        "            margin: 0 0 0.5rem 0;",
        "            color: var(--text-color);",
        "        }",
        "        .disclaimer {",
        "            font-size: 0.95rem;",
        "            color: var(--danger-color);",
        "            background-color: rgba(239, 68, 68, 0.1);",
        "            border-left: 4px solid var(--danger-color);",
        "            padding: 0.75rem 1rem;",
        "            border-radius: 4px;",
        "            margin-bottom: 1.5rem;",
        "            font-weight: 500;",
        "        }",
        "        table {",
        "            width: 100%;",
        "            border-collapse: collapse;",
        "            background-color: var(--card-bg);",
        "            border-radius: 8px;",
        "            overflow: hidden;",
        "            border: 1px solid var(--border-color);",
        "            margin-top: 1rem;",
        "        }",
        "        th, td {",
        "            padding: 1rem;",
        "            text-align: left;",
        "            border-bottom: 1px solid var(--border-color);",
        "            font-size: 0.9rem;",
        "            vertical-align: top;",
        "        }",
        "        th {",
        "            background-color: rgba(51, 65, 85, 0.5);",
        "            font-weight: 600;",
        "            text-transform: uppercase;",
        "            font-size: 0.75rem;",
        "            letter-spacing: 0.05em;",
        "            color: var(--muted-color);",
        "        }",
        "        tr:last-child td {",
        "            border-bottom: none;",
        "        }",
        "        tr:hover {",
        "            background-color: rgba(51, 65, 85, 0.2);",
        "        }",
        "        .badge {",
        "            display: inline-block;",
        "            padding: 0.25rem 0.5rem;",
        "            border-radius: 4px;",
        "            font-size: 0.75rem;",
        "            font-weight: 600;",
        "            text-transform: uppercase;",
        "            white-space: nowrap;",
        "        }",
        "        .badge-success {",
        "            background-color: rgba(16, 185, 129, 0.15);",
        "            color: var(--success-color);",
        "        }",
        "        .badge-warning {",
        "            background-color: rgba(245, 158, 11, 0.15);",
        "            color: var(--warning-color);",
        "        }",
        "        .badge-danger {",
        "            background-color: rgba(239, 68, 68, 0.15);",
        "            color: var(--danger-color);",
        "        }",
        "        .badge-info {",
        "            background-color: rgba(56, 189, 248, 0.15);",
        "            color: var(--accent-color);",
        "        }",
        "        .warnings-list {",
        "            margin: 0;",
        "            padding-left: 1.2rem;",
        "            color: var(--warning-color);",
        "            font-size: 0.85rem;",
        "        }",
        "        .doi-link {",
        "            color: var(--accent-color);",
        "            text-decoration: none;",
        "        }",
        "        .doi-link:hover {",
        "            text-decoration: underline;",
        "        }",
        "    </style>",
        "</head>",
        "<body>",
        '    <div class="container">',
        "        <header>",
        "            <h1>Metadata Review Batch Dashboard</h1>",
        '            <div class="disclaimer">',
        "                This table reports metadata review signals only and does not determine research misconduct.",
        "            </div>",
        "        </header>",
        "        <table>",
        "            <thead>",
        "                <tr>",
        "                    <th>Item ID</th>",
        "                    <th>Title</th>",
        "                    <th>DOI</th>",
        "                    <th>Year</th>",
        "                    <th>Journal</th>",
        "                    <th>Source</th>",
        "                    <th>Crossref Update</th>",
        "                    <th>Metadata Status</th>",
        "                    <th>Warnings</th>",
        "                    <th>Manual Review?</th>",
        "                </tr>",
        "            </thead>",
        "            <tbody>",
    ]

    for item in items:
        item_id = html.escape(str(item.get("item_id", "")))
        title = html.escape(str(item.get("title") or ""))
        doi = html.escape(str(item.get("doi") or ""))
        normalized_doi = html.escape(str(item.get("normalized_doi") or ""))
        year = html.escape(str(item.get("year") or ""))
        journal = html.escape(str(item.get("journal") or ""))
        source_format = html.escape(str(item.get("source_format", "")))
        crossref_update = html.escape(str(item.get("crossref_update_status", "metadata_unavailable")))
        metadata_status = html.escape(str(item.get("metadata_status", "offline")))
        warnings = item.get("warnings", [])

        # Determine Manual Review Requirement
        requires_manual = False
        if not item.get("normalized_doi"):
            requires_manual = True
        elif item.get("metadata_status") != "success":
            requires_manual = True
        elif item.get("crossref_update_status") in ["retraction", "correction", "expression_of_concern"]:
            requires_manual = True

        manual_badge = (
            '<span class="badge badge-danger">Required</span>'
            if requires_manual
            else '<span class="badge badge-success">No</span>'
        )

        # DOI Link
        doi_display = (
            f'<a class="doi-link" href="https://doi.org/{normalized_doi}" target="_blank">{normalized_doi}</a>'
            if normalized_doi
            else f'<span style="color: var(--muted-color);">{doi}</span>'
        )

        # Crossref Update Status Badge
        update_cls = "badge-success"
        if crossref_update in ["retraction", "reinstatement"]:
            update_cls = "badge-danger"
        elif crossref_update in ["correction", "expression_of_concern"]:
            update_cls = "badge-warning"
        elif crossref_update == "metadata_unavailable":
            update_cls = "badge-info"
        update_badge = f'<span class="badge {update_cls}">{crossref_update}</span>'

        # Metadata Lookup Status Badge
        status_cls = "badge-success"
        if metadata_status != "success":
            status_cls = "badge-danger" if metadata_status == "failed" else "badge-info"
        status_badge = f'<span class="badge {status_cls}">{metadata_status}</span>'

        # Warnings formatting
        warnings_html = ""
        if warnings:
            warnings_html = '<ul class="warnings-list">'
            for w in warnings:
                warnings_html += f"<li>{html.escape(w)}</li>"
            warnings_html += "</ul>"

        html_lines.append("                <tr>")
        html_lines.append(f"                    <td><code>{item_id}</code></td>")
        html_lines.append(f"                    <td><strong>{title or '<em>Untitled</em>'}</strong></td>")
        html_lines.append(f"                    <td>{doi_display}</td>")
        html_lines.append(f"                    <td>{year}</td>")
        html_lines.append(f"                    <td>{journal}</td>")
        html_lines.append(f"                    <td><span class=\"badge badge-info\">{source_format}</span></td>")
        html_lines.append(f"                    <td>{update_badge}</td>")
        html_lines.append(f"                    <td>{status_badge}</td>")
        html_lines.append(f"                    <td>{warnings_html}</td>")
        html_lines.append(f"                    <td>{manual_badge}</td>")
        html_lines.append("                </tr>")

    html_lines.extend([
        "            </tbody>",
        "        </table>",
        "    </div>",
        "</body>",
        "</html>",
    ])

    resolved_out.write_text("\n".join(html_lines), encoding="utf-8")
    return resolved_out.resolve()
