from __future__ import annotations

import json
from pathlib import Path
import html

def generate_pv_domain_html(
    findings_path: Path | str,
    output_path: Path | str | None = None
) -> Path:
    findings_path = Path(findings_path)
    if not findings_path.exists():
        raise FileNotFoundError(f"Findings file not found: {findings_path}")

    # Determine output path
    if output_path is None:
        resolved_out = findings_path.parent / "pv_domain_dashboard.html"
    else:
        resolved_out = Path(output_path)
        resolved_out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load findings
    findings = []
    with findings_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # 2. Try loading total rows from metric_rows.jsonl
    metric_rows_path = findings_path.parent / "pv_metric_rows.jsonl"
    total_rows = 0
    if metric_rows_path.exists():
        try:
            with metric_rows_path.open(encoding="utf-8") as f:
                total_rows = sum(1 for line in f if line.strip())
        except Exception:
            pass

    # 3. Count categories
    pce_cnt = sum(1 for f in findings if f["rule_id"] == "pv_pce_consistency")
    eqe_cnt = sum(1 for f in findings if f["rule_id"] == "pv_eqe_jv_jsc_consistency")
    voc_cnt = sum(1 for f in findings if f["rule_id"] == "pv_voc_loss_consistency")
    rep_cnt = sum(1 for f in findings if f["rule_id"] == "pv_reporting_completeness")
    stab_cnt = sum(1 for f in findings if f["rule_id"] == "pv_stability_reporting_completeness")
    tan_cnt = sum(1 for f in findings if f["rule_id"] == "pv_tandem_current_matching")
    mat_cnt = sum(1 for f in findings if f["rule_id"] == "pv_materials_characterization_metadata")

    # Render finding rows
    tbody_html = ""
    for f in findings:
        risk_class = f"risk-{f['risk_level']}"
        row_idx_str = f"Row {f['row_index']}" if f.get("row_index") is not None else "Table-level"
        device_id_str = f["device_id"] if f.get("device_id") else "N/A"
        
        # Format observed and recomputed values as clean JSON-like key-value lists
        def format_dict(d):
            if not d:
                return "<span class='empty-val'>None</span>"
            items = []
            for k, v in d.items():
                if isinstance(v, float):
                    items.append(f"<div class='val-item'><strong>{k}</strong>: {v:.4f}</div>")
                else:
                    items.append(f"<div class='val-item'><strong>{k}</strong>: {v}</div>")
            return "".join(items)

        obs_html = format_dict(f.get("observed_values", {}))
        rec_html = format_dict(f.get("recomputed_values", {}))
        
        mv_list_html = "".join([f"<li>{html.escape(mv)}</li>" for mv in f.get("manual_verification", [])])

        tbody_html += f"""
        <tr class="finding-row {risk_class}">
            <td class="col-id"><strong>{html.escape(f['finding_id'])}</strong></td>
            <td class="col-rule">
                <span class="rule-badge">{html.escape(f['rule_id'].replace('pv_', ''))}</span>
                <span class="risk-badge badge-{f['risk_level']}">{f['risk_level'].upper()}</span>
            </td>
            <td class="col-file">
                <div class="file-name">{html.escape(f['source_file'])}</div>
                <div class="table-id">Table: {html.escape(f['table_id'])}</div>
            </td>
            <td class="col-loc">
                <div class="loc-index">{html.escape(row_idx_str)}</div>
                <div class="device-id">Device: {html.escape(device_id_str)}</div>
            </td>
            <td class="col-values">
                <div class="obs-box">
                    <span class="box-lbl">Observed</span>
                    {obs_box_with_padding(obs_html)}
                </div>
                <div class="rec-box">
                    <span class="box-lbl">Recomputed</span>
                    {obs_box_with_padding(rec_html)}
                </div>
            </td>
            <td class="col-lang">{html.escape(f['safe_report_language'])}</td>
            <td class="col-mv">
                <ul class="mv-list">
                    {mv_list_html}
                </ul>
            </td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photovoltaics & Materials Domain Review Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 29, 49, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #0ea5e9;
            --accent-green: #10b981;
            --accent-rose: #f43f5e;
            --accent-amber: #f59e0b;
            --glass-glow: rgba(14, 165, 233, 0.15);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.5;
            background-image: 
                radial-gradient(at 10% 20%, rgba(14, 165, 233, 0.1) 0px, transparent 50%),
                radial-gradient(at 90% 10%, rgba(244, 63, 94, 0.08) 0px, transparent 50%),
                radial-gradient(at 50% 80%, rgba(16, 185, 129, 0.05) 0px, transparent 50%);
            background-attachment: fixed;
        }}

        header {{
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        .header-title-container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            flex-wrap: wrap;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.25rem;
            font-weight: 700;
            background: linear-gradient(135deg, #fff 0%, var(--text-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }}

        .safety-notice {{
            background: rgba(245, 158, 11, 0.08);
            border: 1px solid rgba(255, 158, 11, 0.25);
            padding: 1rem 1.25rem;
            border-radius: 12px;
            margin-top: 1.25rem;
            font-size: 0.925rem;
            color: #ffedd5;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            backdrop-filter: blur(8px);
        }}

        .safety-notice svg {{
            flex-shrink: 0;
            color: var(--accent-amber);
        }}

        /* Stats Bento Grid */
        .bento-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2.5rem;
        }}

        .bento-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.3s, box-shadow 0.3s;
            position: relative;
            overflow: hidden;
        }}

        .bento-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(255, 255, 255, 0.1) inset;
        }}

        .bento-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
        }}

        .card-label {{
            font-size: 0.825rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}

        .card-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .bento-card.primary {{
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.15) 0%, rgba(22, 29, 49, 0.7) 100%);
            border-color: rgba(14, 165, 233, 0.3);
        }}
        .bento-card.primary::before {{
            background: linear-gradient(90deg, transparent, var(--accent-blue), transparent);
        }}

        /* Table Card */
        .table-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            overflow: hidden;
            backdrop-filter: blur(12px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}

        .table-header {{
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .table-header h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            font-weight: 600;
        }}

        .findings-table-wrapper {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }}

        th {{
            background: rgba(15, 23, 42, 0.6);
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
        }}

        td {{
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
            vertical-align: top;
        }}

        .finding-row {{
            transition: background-color 0.2s;
        }}

        .finding-row:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}

        .col-id {{
            color: var(--accent-blue);
            font-size: 0.85rem;
            white-space: nowrap;
        }}

        .col-rule {{
            min-width: 150px;
        }}

        .rule-badge {{
            display: block;
            font-size: 0.75rem;
            background: rgba(255,255,255,0.05);
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            color: var(--text-primary);
            border: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 0.5rem;
            width: fit-content;
            font-family: monospace;
        }}

        .risk-badge {{
            display: inline-block;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            letter-spacing: 0.05em;
        }}

        .badge-medium {{
            background: rgba(244, 63, 94, 0.15);
            color: #fda4af;
            border: 1px solid rgba(244, 63, 94, 0.3);
        }}

        .badge-low {{
            background: rgba(245, 158, 11, 0.15);
            color: #fde047;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .file-name {{
            font-weight: 600;
            color: var(--text-primary);
            word-break: break-all;
        }}

        .table-id {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }}

        .loc-index {{
            font-weight: 500;
        }}

        .device-id {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }}

        .col-values {{
            min-width: 200px;
        }}

        .obs-box, .rec-box {{
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.6rem 0.8rem;
            margin-bottom: 0.5rem;
            font-size: 0.8rem;
            position: relative;
        }}

        .box-lbl {{
            position: absolute;
            right: 0.6rem;
            top: 0.4rem;
            font-size: 0.65rem;
            text-transform: uppercase;
            color: var(--text-secondary);
            font-weight: 600;
            letter-spacing: 0.05em;
        }}

        .val-item {{
            margin-top: 0.25rem;
        }}

        .val-item strong {{
            color: var(--text-secondary);
        }}

        .empty-val {{
            color: var(--text-secondary);
            font-style: italic;
        }}

        .col-lang {{
            font-size: 0.85rem;
            color: #e2e8f0;
            min-width: 250px;
            line-height: 1.4;
        }}

        .col-mv {{
            min-width: 280px;
        }}

        .mv-list {{
            padding-left: 1.1rem;
            font-size: 0.825rem;
            color: var(--text-secondary);
        }}

        .mv-list li {{
            margin-bottom: 0.4rem;
        }}

        /* Empty state */
        .no-findings {{
            padding: 4rem 2rem;
            text-align: center;
            color: var(--text-secondary);
        }}
        
        .no-findings svg {{
            margin-bottom: 1rem;
            color: var(--accent-green);
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-title-container">
            <h1>Photovoltaics & Materials Domain Review</h1>
        </div>
        <div class="safety-notice">
            <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span><strong>Safety Notice:</strong> This dashboard reports photovoltaic/materials domain consistency signals only and does not determine data fabrication or research misconduct.</span>
        </div>
    </header>

    <main>
        <div class="bento-grid">
            <div class="bento-card primary">
                <div class="card-label">Total PV Rows</div>
                <div class="card-value">{total_rows if total_rows > 0 else len(findings)}</div>
            </div>
            <div class="bento-card">
                <div class="card-label">PCE Findings</div>
                <div class="card-value">{pce_cnt}</div>
            </div>
            <div class="bento-card">
                <div class="card-label">EQE/JV Findings</div>
                <div class="card-value">{eqe_cnt}</div>
            </div>
            <div class="bento-card">
                <div class="card-label">Reporting Gaps</div>
                <div class="card-value">{rep_cnt + stab_cnt + mat_cnt}</div>
            </div>
            <div class="bento-card">
                <div class="card-label">Tandem Findings</div>
                <div class="card-value">{tan_cnt}</div>
            </div>
        </div>

        <div class="table-card">
            <div class="table-header">
                <h2>Domain Specific Candidate Risk Signals</h2>
            </div>
            
            <div class="findings-table-wrapper">
                {"<table><thead><tr><th>ID</th><th>Rule / Risk</th><th>Source Table</th><th>Location</th><th>Observed / Recomputed</th><th>Safe Language Description</th><th>Manual Verification Checklist</th></tr></thead><tbody>" + tbody_html + "</tbody></table>" if findings else "<div class='no-findings'><svg width='48' height='48' fill='none' viewBox='0 0 24 24' stroke='currentColor' stroke-width='1.5'><path stroke-linecap='round' stroke-linejoin='round' d='M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' /></svg><p>No photovoltaic or materials consistency signals detected.</p></div>"}
            </div>
        </div>
    </main>
</body>
</html>
"""

    resolved_out.write_text(html_content, encoding="utf-8")
    return resolved_out

def obs_box_with_padding(html_str):
    if "val-item" in html_str:
        return f"<div style='margin-top: 1.2rem;'>{html_str}</div>"
    return html_str
