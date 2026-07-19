from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path

from integrity_agent.core.output_safety import safe_local_asset_url

DEFAULT_OUTPUT_HTML = Path("outputs") / "image_intake" / "image_contact_sheet.html"


def generate_image_contact_sheet(
    manifest_jsonl_path: Path | str,
    output_path: Path | str | None = None,
) -> Path:
    """Generate a static HTML contact sheet dashboard visualizing all images."""
    manifest_jsonl_path = Path(manifest_jsonl_path)
    if not manifest_jsonl_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_jsonl_path}")

    if output_path is None:
        resolved_out = DEFAULT_OUTPUT_HTML
    else:
        resolved_out = Path(output_path)

    resolved_out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Parse all items
    items = []
    with manifest_jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    # 2. Count SHA256 frequencies for duplicate groups
    hash_counts = defaultdict(int)
    for item in items:
        sha = item.get("sha256")
        if sha and sha != "unknown" and not sha.startswith("error"):
            hash_counts[sha] += 1

    # HTML building block template
    html_lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "    <title>Image Intake Contact Sheet</title>",
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
        "            max-width: 1600px;",
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
        "        .grid {",
        "            display: grid;",
        "            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));",
        "            gap: 1.5rem;",
        "            margin-top: 1rem;",
        "        }",
        "        .card {",
        "            background-color: var(--card-bg);",
        "            border: 1px solid var(--border-color);",
        "            border-radius: 8px;",
        "            overflow: hidden;",
        "            display: flex;",
        "            flex-direction: column;",
        "            transition: transform 0.2s, border-color 0.2s;",
        "        }",
        "        .card:hover {",
        "            transform: translateY(-2px);",
        "            border-color: var(--accent-color);",
        "        }",
        "        .image-preview {",
        "            height: 200px;",
        "            background-color: #020617;",
        "            display: flex;",
        "            align-items: center;",
        "            justify-content: center;",
        "            border-bottom: 1px solid var(--border-color);",
        "            overflow: hidden;",
        "            position: relative;",
        "        }",
        "        .image-preview img {",
        "            max-width: 100%;",
        "            max-height: 100%;",
        "            object-fit: contain;",
        "        }",
        "        .placeholder {",
        "            color: var(--muted-color);",
        "            font-size: 0.85rem;",
        "            text-align: center;",
        "            padding: 1rem;",
        "        }",
        "        .card-content {",
        "            padding: 1.2rem;",
        "            display: flex;",
        "            flex-direction: column;",
        "            flex-grow: 1;",
        "            font-size: 0.85rem;",
        "        }",
        "        .card-title {",
        "            font-weight: 700;",
        "            font-size: 0.95rem;",
        "            margin: 0 0 0.5rem 0;",
        "            color: var(--text-color);",
        "            word-break: break-all;",
        "        }",
        "        .meta-row {",
        "            display: flex;",
        "            justify-content: space-between;",
        "            margin-bottom: 0.25rem;",
        "        }",
        "        .meta-label {",
        "            color: var(--muted-color);",
        "        }",
        "        .meta-value {",
        "            font-family: monospace;",
        "            font-weight: 500;",
        "        }",
        "        .badge {",
        "            display: inline-block;",
        "            padding: 0.2rem 0.4rem;",
        "            border-radius: 4px;",
        "            font-size: 0.7rem;",
        "            font-weight: 700;",
        "            text-transform: uppercase;",
        "            margin-top: auto;",
        "            text-align: center;",
        "        }",
        "        .badge-danger {",
        "            background-color: rgba(239, 68, 68, 0.15);",
        "            color: var(--danger-color);",
        "            border: 1px solid var(--danger-color);",
        "        }",
        "        .badge-warning {",
        "            background-color: rgba(245, 158, 11, 0.15);",
        "            color: var(--warning-color);",
        "            border: 1px solid var(--warning-color);",
        "        }",
        "    </style>",
        "</head>",
        "<body>",
        '    <div class="container">',
        "        <header>",
        "            <h1>Image Intake Contact Sheet</h1>",
        '            <div class="disclaimer">',
        "                This contact sheet reports image file-level evidence only and does not determine image manipulation or research misconduct.",
        "            </div>",
        "        </header>",
        '        <div class="grid">',
    ]

    for item in items:
        image_id = html.escape(str(item.get("image_id", "")), quote=True)
        file_name = html.escape(str(item.get("file_name", "")), quote=True)
        file_ext = html.escape(str(item.get("file_ext", "")), quote=True)
        relative_path = str(item.get("relative_path", ""))
        width = int(item.get("width", 0))
        height = int(item.get("height", 0))
        fmt = html.escape(str(item.get("format", "unknown")), quote=True)
        sha256_raw = str(item.get("sha256", ""))
        warnings = item.get("warnings", [])

        # Compute relative image file path from the output HTML location
        # Project relative: e.g. outputs/image_intake/image_manifest.jsonl
        # Image is: e.g. examples/toy_image_package/images/img_a.png
        # We find absolute project root and build relative path
        project_root = Path(__file__).resolve().parents[2]
        rel_img_url = safe_local_asset_url(
            relative_path,
            project_root=project_root,
            output_parent=resolved_out.parent,
        )
        if rel_img_url is not None:
            rel_img_url = html.escape(rel_img_url, quote=True)

        # Check duplicate badge
        is_dup = hash_counts[sha256_raw] > 1 if sha256_raw else False
        badge_html = ""
        if is_dup:
            badge_html = '<span class="badge badge-danger">Exact Duplicate</span>'
        elif warnings:
            badge_html = '<span class="badge badge-warning">Corrupted / Failed</span>'

        # Render preview tag
        if warnings or rel_img_url is None:
            preview_html = '<div class="placeholder">Failed to render preview<br><small style="color: var(--danger-color);">Metadata read failed</small></div>'
        else:
            preview_html = f'<img src="{rel_img_url}" alt="{file_name}" loading="lazy">'

        sha_short = html.escape(sha256_raw[:12], quote=True) if sha256_raw else "unknown"

        html_lines.extend([
            '            <div class="card">',
            '                <div class="image-preview">',
            f"                    {preview_html}",
            "                </div>",
            '                <div class="card-content">',
            f'                    <div class="card-title"><code>{image_id}</code> - {file_name}{file_ext}</div>',
            '                    <div class="meta-row">',
            '                        <span class="meta-label">Dimensions:</span>',
            f'                        <span class="meta-value">{width} x {height}</span>',
            "                    </div>",
            '                    <div class="meta-row">',
            '                        <span class="meta-label">Format:</span>',
            f'                        <span class="meta-value">{fmt}</span>',
            "                    </div>",
            '                    <div class="meta-row">',
            '                        <span class="meta-label">SHA256 (short):</span>',
            f'                        <span class="meta-value">{sha_short}</span>',
            "                    </div>",
            f"                    {badge_html}",
            "                </div>",
            "            </div>",
        ])

    html_lines.extend([
        "        </div>",
        "    </div>",
        "</body>",
        "</html>",
    ])

    resolved_out.write_text("\n".join(html_lines), encoding="utf-8")
    return resolved_out.resolve()
