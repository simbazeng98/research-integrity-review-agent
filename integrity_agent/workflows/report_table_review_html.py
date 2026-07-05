from __future__ import annotations

import html
import json
from pathlib import Path

DEFAULT_OUTPUT_HTML = Path("outputs") / "table_intake" / "table_review_dashboard.html"


def generate_table_review_html(
    manifest_jsonl_path: Path | str,
    output_path: Path | str | None = None,
) -> Path:
    """Generate a static HTML dashboard visualizing extracted tables, profiles, and numeric findings."""
    manifest_jsonl_path = Path(manifest_jsonl_path)
    if not manifest_jsonl_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_jsonl_path}")

    resolved_out = DEFAULT_OUTPUT_HTML if output_path is None else Path(output_path)
    resolved_out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load manifest items
    items = []
    with manifest_jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    # 2. Try loading column profiles to identify numeric columns
    profiles_path = manifest_jsonl_path.parent / "column_profiles.jsonl"
    numeric_cols_by_table: dict[str, list[str]] = {}
    if profiles_path.exists():
        with profiles_path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    t_id = rec["table_id"]
                    prof = rec["profile"]
                    if prof["inferred_type"] in ["integer", "float"]:
                        numeric_cols_by_table.setdefault(t_id, []).append(prof["column_name"])

    # 3. Try loading numeric findings to display badges
    findings_path = manifest_jsonl_path.parent / "table_numeric_findings.jsonl"
    findings_by_table: dict[str, list[dict]] = {}
    if findings_path.exists():
        with findings_path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    find = json.loads(line)
                    t_id = find["table_id"]
                    findings_by_table.setdefault(t_id, []).append(find)

    # HTML design
    html_lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "    <title>Source Data Table Review Dashboard</title>",
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
        "            max-width: 1200px;",
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
        "            margin-top: 1.5rem;",
        "            background-color: var(--card-bg);",
        "            border-radius: 8px;",
        "            overflow: hidden;",
        "            border: 1px solid var(--border-color);",
        "        }",
        "        th, td {",
        "            padding: 0.85rem 1rem;",
        "            text-align: left;",
        "            border-bottom: 1px solid var(--border-color);",
        "        }",
        "        th {",
        "            background-color: rgba(51, 65, 85, 0.4);",
        "            font-weight: 600;",
        "            font-size: 0.9rem;",
        "            color: var(--muted-color);",
        "        }",
        "        tr:last-child td {",
        "            border-bottom: none;",
        "        }",
        "        .badge {",
        "            display: inline-block;",
        "            padding: 0.2rem 0.4rem;",
        "            border-radius: 4px;",
        "            font-size: 0.75rem;",
        "            font-weight: 700;",
        "            text-transform: uppercase;",
        "            margin-right: 0.4rem;",
        "        }",
        "        .badge-success {",
        "            background-color: rgba(16, 185, 129, 0.15);",
        "            color: var(--success-color);",
        "            border: 1px solid var(--success-color);",
        "        }",
        "        .badge-warning {",
        "            background-color: rgba(245, 158, 11, 0.15);",
        "            color: var(--warning-color);",
        "            border: 1px solid var(--warning-color);",
        "        }",
        "        .badge-danger {",
        "            background-color: rgba(239, 68, 68, 0.15);",
        "            color: var(--danger-color);",
        "            border: 1px solid var(--danger-color);",
        "        }",
        "        .warning-text {",
        "            color: var(--warning-color);",
        "            font-size: 0.85rem;",
        "        }",
        "        code {",
        "            font-family: monospace;",
        "            background-color: rgba(15, 23, 42, 0.6);",
        "            padding: 0.1rem 0.3rem;",
        "            border-radius: 3px;",
        "            font-size: 0.85rem;",
        "        }",
        "    </style>",
        "</head>",
        "<body>",
        '    <div class="container">',
        "        <header>",
        "            <h1>Source Data Table Review Dashboard</h1>",
        '            <div class="disclaimer">',
        "                This dashboard reports source-data table signals only and does not determine data fabrication or research misconduct.",
        "            </div>",
        "        </header>",
        "        <table>",
        "            <thead>",
        "                <tr>",
        "                    <th>Table ID</th>",
        "                    <th>Source File</th>",
        "                    <th>Sheet Name</th>",
        "                    <th>Format</th>",
        "                    <th>Size</th>",
        "                    <th>Numeric Columns</th>",
        "                    <th>Findings / Risk Badges</th>",
        "                    <th>Warnings</th>",
        "                </tr>",
        "            </thead>",
        "            <tbody>",
    ]

    for item in items:
        t_id = html.escape(str(item.get("table_id", "")))
        src_file = html.escape(str(item.get("source_file", "")))
        sheet = html.escape(str(item.get("sheet_name", "") or "-"))
        fmt = html.escape(str(item.get("source_format", "")))
        rows_count = item.get("row_count", 0)
        cols_count = item.get("column_count", 0)
        size_str = f"{rows_count} rows x {cols_count} cols"

        # Numeric columns list
        num_cols = numeric_cols_by_table.get(t_id, [])
        num_cols_str = ", ".join(f"<code>{html.escape(c)}</code>" for c in num_cols) if num_cols else "-"

        # Badges for findings
        t_findings = findings_by_table.get(t_id, [])
        badges = []
        if t_findings:
            # Group by rule_id
            rules_found = set(f["rule_id"] for f in t_findings)
            for r_id in rules_found:
                short_name = r_id.replace("numeric_", "").replace("_between_columns", "").replace("_anomaly", "").replace("_", " ")
                badges.append(f'<span class="badge badge-danger">{html.escape(short_name)}</span>')
        else:
            badges.append('<span class="badge badge-success">No Findings</span>')

        badges_str = " ".join(badges)

        # Warnings cell
        warns = item.get("warnings", [])
        warns_str = ", ".join(f'<span class="warning-text">{html.escape(w)}</span>' for w in warns) if warns else "-"

        html_lines.extend([
            "                <tr>",
            f"                    <td><strong>{t_id}</strong></td>",
            f"                    <td>{src_file}</td>",
            f"                    <td>{sheet}</td>",
            f"                    <td><code>{fmt}</code></td>",
            f"                    <td>{size_str}</td>",
            f"                    <td>{num_cols_str}</td>",
            f"                    <td>{badges_str}</td>",
            f"                    <td>{warns_str}</td>",
            "                </tr>",
        ])

    html_lines.extend([
        "            </tbody>",
        "        </table>",
        "    </div>",
        "</body>",
        "</html>",
    ])

    resolved_out.write_text("\n".join(html_lines), encoding="utf-8")
    return resolved_out.resolve()
