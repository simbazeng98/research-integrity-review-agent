from __future__ import annotations

import html
import json
from pathlib import Path
from PIL import Image

from integrity_agent.core.output_safety import resolve_local_asset, safe_local_asset_url

DEFAULT_OUTPUT_HTML = Path("outputs") / "image_intake" / "image_similarity_pairs.html"


def generate_similarity_pairs_html(
    candidates_jsonl_path: Path | str,
    output_path: Path | str | None = None,
) -> Path:
    """Generate a static HTML contact sheet displaying visual similarity candidate pairs side-by-side."""
    candidates_jsonl_path = Path(candidates_jsonl_path)
    if not candidates_jsonl_path.exists():
        raise FileNotFoundError(f"Candidates file not found: {candidates_jsonl_path}")

    if output_path is None:
        resolved_out = DEFAULT_OUTPUT_HTML
    else:
        resolved_out = Path(output_path)

    resolved_out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load candidates
    candidates = []
    with candidates_jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))

    # 2. Try to load image manifest from the same directory for image details
    manifest_path = candidates_jsonl_path.parent / "image_manifest.jsonl"
    manifest_lookup: dict[str, dict] = {}
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    manifest_lookup[item["image_id"]] = item

    project_root = Path.cwd()

    # HTML structure template
    html_lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "    <title>Image Similarity Pairs Review</title>",
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
        "        .pair-container {",
        "            border: 1px solid var(--border-color);",
        "            background-color: var(--card-bg);",
        "            border-radius: 8px;",
        "            margin-bottom: 2rem;",
        "            padding: 1.5rem;",
        "        }",
        "        .pair-header {",
        "            display: flex;",
        "            justify-content: space-between;",
        "            align-items: center;",
        "            margin-bottom: 1rem;",
        "            padding-bottom: 0.5rem;",
        "            border-bottom: 1px solid var(--border-color);",
        "        }",
        "        .pair-title {",
        "            font-weight: 700;",
        "            font-size: 1.1rem;",
        "            color: var(--accent-color);",
        "        }",
        "        .pair-grid {",
        "            display: grid;",
        "            grid-template-columns: 1fr 1fr;",
        "            gap: 1.5rem;",
        "        }",
        "        .image-column {",
        "            display: flex;",
        "            flex-direction: column;",
        "            align-items: center;",
        "        }",
        "        .image-box {",
        "            height: 250px;",
        "            background-color: #020617;",
        "            display: flex;",
        "            align-items: center;",
        "            justify-content: center;",
        "            border: 1px solid var(--border-color);",
        "            border-radius: 4px;",
        "            overflow: hidden;",
        "            width: 100%;",
        "            margin-bottom: 0.75rem;",
        "        }",
        "        .image-box img {",
        "            max-width: 100%;",
        "            max-height: 100%;",
        "            object-fit: contain;",
        "        }",
        "        .image-label {",
        "            font-weight: 600;",
        "            font-size: 0.85rem;",
        "            text-align: center;",
        "            word-break: break-all;",
        "        }",
        "        .image-dim {",
        "            color: var(--muted-color);",
        "            font-size: 0.8rem;",
        "        }",
        "        .pair-meta {",
        "            display: flex;",
        "            justify-content: space-between;",
        "            font-size: 0.85rem;",
        "            color: var(--muted-color);",
        "            background-color: rgba(51, 65, 85, 0.2);",
        "            padding: 0.75rem 1rem;",
        "            border-radius: 4px;",
        "            margin-top: 1rem;",
        "        }",
        "        .badge {",
        "            display: inline-block;",
        "            padding: 0.2rem 0.4rem;",
        "            border-radius: 4px;",
        "            font-size: 0.7rem;",
        "            font-weight: 700;",
        "            text-transform: uppercase;",
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
        "            <h1>Image Similarity Pairs Review</h1>",
        '            <div class="disclaimer">',
        "                This report shows candidate visual similarity pairs only and does not determine image manipulation or research misconduct.",
        "            </div>",
        "        </header>",
    ]

    for cand in candidates:
        cand_id = html.escape(str(cand.get("candidate_id", "")), quote=True)
        id_a_raw = str(cand.get("image_id_a", ""))
        id_b_raw = str(cand.get("image_id_b", ""))
        id_a = html.escape(id_a_raw, quote=True)
        id_b = html.escape(id_b_raw, quote=True)
        path_a = str(cand.get("relative_path_a", ""))
        path_b = str(cand.get("relative_path_b", ""))
        method = html.escape(str(cand.get("hash_method", "")), quote=True)
        distance = int(cand.get("hamming_distance", 0))
        threshold = int(cand.get("threshold", 0))

        # Lookup details or load images to get dimensions
        dim_a = "unknown"
        dim_b = "unknown"

        if id_a_raw in manifest_lookup:
            dim_a = f"{manifest_lookup[id_a_raw]['width']} x {manifest_lookup[id_a_raw]['height']}"
        if id_b_raw in manifest_lookup:
            dim_b = f"{manifest_lookup[id_b_raw]['width']} x {manifest_lookup[id_b_raw]['height']}"

        # Resolve only project-contained assets. Avoid broad recursive searches
        # and never embed paths that escape the local project root.
        abs_a = resolve_local_asset(path_a, project_root=project_root)
        abs_b = resolve_local_asset(path_b, project_root=project_root)
        name_a = html.escape(abs_a.name, quote=True) if abs_a is not None else "unavailable"
        name_b = html.escape(abs_b.name, quote=True) if abs_b is not None else "unavailable"

        # Read dimensions if we couldn't get them from manifest lookup
        if dim_a == "unknown" and abs_a is not None and abs_a.exists():
            try:
                with Image.open(abs_a) as im:
                    dim_a = f"{im.width} x {im.height}"
            except Exception:
                pass
        if dim_b == "unknown" and abs_b is not None and abs_b.exists():
            try:
                with Image.open(abs_b) as im:
                    dim_b = f"{im.width} x {im.height}"
            except Exception:
                pass

        url_a = safe_local_asset_url(
            path_a,
            project_root=project_root,
            output_parent=resolved_out.parent,
        )
        url_b = safe_local_asset_url(
            path_b,
            project_root=project_root,
            output_parent=resolved_out.parent,
        )
        if url_a is not None:
            url_a = html.escape(url_a, quote=True)
        if url_b is not None:
            url_b = html.escape(url_b, quote=True)
        dim_a = html.escape(str(dim_a), quote=True)
        dim_b = html.escape(str(dim_b), quote=True)

        html_lines.extend([
            '        <div class="pair-container">',
            '            <div class="pair-header">',
            f'                <span class="pair-title">Candidate Pair: {cand_id}</span>',
            '                <span class="badge badge-warning">Visual Similarity Candidate</span>',
            "            </div>",
            '            <div class="pair-grid">',
            '                <div class="image-column">',
            '                    <div class="image-box">',
            (
                f'                        <img src="{url_a}" alt="{name_a}">'
                if url_a is not None
                else '                        <div class="image-unavailable">Preview unavailable</div>'
            ),
            "                    </div>",
            f'                    <div class="image-label"><code>{id_a}</code> - {name_a}</div>',
            f'                    <div class="image-dim">Dimensions: {dim_a}</div>',
            "                </div>",
            '                <div class="image-column">',
            '                    <div class="image-box">',
            (
                f'                        <img src="{url_b}" alt="{name_b}">'
                if url_b is not None
                else '                        <div class="image-unavailable">Preview unavailable</div>'
            ),
            "                    </div>",
            f'                    <div class="image-label"><code>{id_b}</code> - {name_b}</div>',
            f'                    <div class="image-dim">Dimensions: {dim_b}</div>',
            "                </div>",
            "            </div>",
            '            <div class="pair-meta">',
            f"                <span>Method: <strong>{method}</strong></span>",
            f"                <span>Hamming Distance: <strong>{distance}</strong> (threshold: {threshold})</span>",
            "            </div>",
            "        </div>",
        ])

    html_lines.extend([
        "    </div>",
        "</body>",
        "</html>",
    ])

    resolved_out.write_text("\n".join(html_lines), encoding="utf-8")
    return resolved_out.resolve()
