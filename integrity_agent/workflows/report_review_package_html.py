from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from integrity_agent.core.path_display import display_path
import sys

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Generate unified review package HTML dashboard.")
    parser.add_argument("unified_index", help="Path to unified_evidence_index.jsonl.")
    parser.add_argument("-o", "--output", default="outputs/review_package/review_package_dashboard.html", help="Path to write dashboard HTML.")
    return parser.parse_args(args)

def run_report_review_package_html(unified_index: str, output_path: str = "outputs/review_package/review_package_dashboard.html") -> str:
    index_path = Path(unified_index)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    findings = []
    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        findings.append(json.loads(line))
        except Exception as e:
            print(f"WARNING: Failed to read unified index: {e}", file=sys.stderr)

    # Calculate statistics
    total_findings = len(findings)
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    for f in findings:
        r = f.get("risk_level", "low").lower()
        if r in risk_counts:
            risk_counts[r] += 1
        else:
            risk_counts["low"] += 1

    # Group findings by category
    metadata_f = []
    image_f = []
    table_f = []
    pv_f = []
    raw_pv_f = []

    for f in findings:
        rule_id = f.get("rule_id", "")
        # Determine category from rule_id or source file or metadata
        if "retraction" in rule_id or "metadata" in rule_id or "doi" in rule_id:
            metadata_f.append(f)
        elif "image" in rule_id or "duplicate" in rule_id or "similarity" in rule_id:
            image_f.append(f)
        elif "numeric" in rule_id or "delta" in rule_id or "digit" in rule_id:
            table_f.append(f)
        elif "raw" in rule_id or "recalculate" in rule_id or "hysteresis" in rule_id or "excel" in rule_id or "integration" in rule_id:
            raw_pv_f.append(f)
        elif "pv_" in rule_id:
            pv_f.append(f)
        else:
            # Fallback
            raw_pv_f.append(f)

    # HTML Template
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified Research Integrity Review Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&amp;family=Outfit:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(17, 24, 39, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            line-height: 1.5;
            padding: 2rem;
        }}

        header {{
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        .safety-notice {{
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.2);
            color: var(--accent-yellow);
            padding: 1rem;
            border-radius: 8px;
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
            font-weight: 500;
            backdrop-filter: blur(10px);
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            backdrop-filter: blur(12px);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
            border-color: rgba(255, 255, 255, 0.15);
        }}

        .stat-card h3 {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }}

        .stat-card p {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            color: #ffffff;
        }}

        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            font-weight: 600;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .section-title::after {{
            content: '';
            flex-grow: 1;
            height: 1px;
            background: var(--border-color);
        }}

        .findings-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .finding-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .finding-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.75rem;
        }}

        .finding-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.2rem;
            font-weight: 600;
            color: #ffffff;
        }}

        .badge {{
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-medium {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-yellow);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-low {{
            background: rgba(59, 130, 246, 0.15);
            color: var(--accent-blue);
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}

        .badge-high {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .details-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
        }}

        .detail-item h4 {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }}

        .detail-item p, .detail-item pre {{
            background: rgba(0, 0, 0, 0.2);
            padding: 0.6rem;
            border-radius: 6px;
            font-size: 0.9rem;
            border: 1px solid rgba(255, 255, 255, 0.03);
            white-space: pre-wrap;
            word-break: break-all;
        }}

        .safe-lang-box {{
            background: rgba(255, 255, 255, 0.02);
            border-left: 3px solid var(--accent-purple);
            padding: 1rem;
            border-radius: 0 8px 8px 0;
            font-style: italic;
            font-size: 0.95rem;
            color: #e5e7eb;
        }}

        .list-box h5 {{
            font-size: 0.9rem;
            color: #ffffff;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }}

        .list-box ul {{
            list-style-type: none;
            padding-left: 0;
        }}

        .list-box li {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.25rem;
            position: relative;
            padding-left: 1rem;
        }}

        .list-box li::before {{
            content: '•';
            color: var(--accent-purple);
            position: absolute;
            left: 0;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}
            .details-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>

    <header>
        <h1>Unified Research Integrity Review Dashboard</h1>
        <p style="color: var(--text-muted);">Unified paper-level review summary &amp; evidence ledger indexing</p>
    </header>

    <div class="safety-notice">
        <strong>Safety Notice:</strong> This dashboard aggregates evidence signals only and does not determine research misconduct.
    </div>

    <section>
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Findings</h3>
                <p>{total_findings}</p>
            </div>
            <div class="stat-card">
                <h3>Medium Risk</h3>
                <p style="color: var(--accent-yellow);">{risk_counts['medium']}</p>
            </div>
            <div class="stat-card">
                <h3>Low Risk</h3>
                <p style="color: var(--accent-blue);">{risk_counts['low']}</p>
            </div>
        </div>
    </section>
    """

    def render_findings_list(title: str, findings_list: list[dict]):
        nonlocal html_content
        if not findings_list:
            return
        
        html_content += f"""
        <section>
            <div class="section-title">{title} ({len(findings_list)})</div>
            <div class="findings-grid">
        """
        
        for f in findings_list:
            fid = f.get("finding_id") or f.get("item_id") or "FINDING"
            rule_id = f.get("rule_id", "unknown_rule")
            det_id = f.get("detector_id", "unknown_detector")
            risk = f.get("risk_level", "low").lower()
            src_file = f.get("source_file") or f.get("relative_path") or "unknown_file"
            
            obs_str = json.dumps(f.get("observed_values", {}), indent=2)
            recomp_str = json.dumps(f.get("recomputed_values", {}), indent=2)
            tol_str = json.dumps(f.get("tolerance", {}), indent=2) if f.get("tolerance") else "N/A"
            
            safe_lang = html.escape(f.get("safe_report_language", ""))
            
            # Build checklist / explanations lists
            alt_exp_html = "".join(f"<li>{html.escape(item)}</li>" for item in f.get("alternative_explanations", []))
            m_verif_html = "".join(f"<li>{html.escape(item)}</li>" for item in f.get("manual_verification", []))
            limits_html = "".join(f"<li>{html.escape(item)}</li>" for item in f.get("limitations", []))

            badge_class = f"badge-{risk}"

            html_content += f"""
                <div class="finding-card">
                    <div class="finding-header">
                        <div>
                            <div class="finding-title">{fid}: {rule_id}</div>
                            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                                Detector: <code>{det_id}</code> | File: <code>{src_file}</code>
                            </div>
                        </div>
                        <span class="badge {badge_class}">{risk}</span>
                    </div>

                    <div class="safe-lang-box">
                        {safe_lang}
                    </div>

                    <div class="details-grid">
                        <div class="detail-item">
                            <h4>Observed Values</h4>
                            <pre><code>{html.escape(obs_str)}</code></pre>
                        </div>
                        <div class="detail-item">
                            <h4>Recomputed / Metadata Values</h4>
                            <pre><code>{html.escape(recomp_str)}</code></pre>
                        </div>
                        <div class="detail-item">
                            <h4>Tolerance / Target</h4>
                            <pre><code>{html.escape(tol_str)}</code></pre>
                        </div>
                    </div>

                    <div class="details-grid" style="border-top: 1px solid var(--border-color); padding-top: 1rem; margin-top: 0.5rem;">
                        <div class="list-box">
                            <h5>Alternative Benign Explanations</h5>
                            <ul>{alt_exp_html}</ul>
                        </div>
                        <div class="list-box">
                            <h5>Manual Verification Protocol</h5>
                            <ul>{m_verif_html}</ul>
                        </div>
                        <div class="list-box">
                            <h5>Limitations</h5>
                            <ul>{limits_html}</ul>
                        </div>
                    </div>
                </div>
            """
        
        html_content += """
            </div>
        </section>
        """

    # Render each section
    render_findings_list("Metadata &amp; Retraction Check Signals", metadata_f)
    render_findings_list("Image Duplicate &amp; Similarity Signals", image_f)
    render_findings_list("Table Numeric Signals", table_f)
    render_findings_list("PV Domain Consistency Signals", pv_f)
    render_findings_list("Raw PV Recalculation &amp; Formula Audit Signals", raw_pv_f)

    html_content += """
</body>
</html>
"""

    out_file.write_text(html_content, encoding="utf-8")
    print(f"Wrote unified dashboard HTML: {display_path(out_file)}")
    return str(out_file)

def main(args=None):
    parsed = parse_args(args)
    run_report_review_package_html(parsed.unified_index, parsed.output)

if __name__ == "__main__":
    main()
