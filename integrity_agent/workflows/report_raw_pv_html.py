from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from integrity_agent.core.path_display import display_path


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Generate raw PV measurement recalculation HTML dashboard.")
    parser.add_argument("findings_jsonl", help="Path to raw_pv_findings.jsonl.")
    parser.add_argument("-o", "--output", default="outputs/raw_pv/raw_pv_dashboard.html", help="Path to write dashboard HTML.")
    return parser.parse_args(args)

def run_report_raw_pv_html(findings_jsonl: str, output_path: str = "outputs/raw_pv/raw_pv_dashboard.html") -> str:
    findings_path = Path(findings_jsonl)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    findings = []
    if findings_path.exists():
        try:
            with open(findings_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        findings.append(json.loads(line))
        except Exception as e:
            print(f"WARNING: Failed to read findings: {e}", file=sys.stderr)

    # Gather counts from other output files if they exist
    out_dir = findings_path.parent
    jv_curves_count = 0
    eqe_spectra_count = 0
    excel_workbooks_count = 0

    try:
        jv_curves_file = out_dir / "jv_curves.jsonl"
        if jv_curves_file.exists():
            with open(jv_curves_file, "r", encoding="utf-8") as f:
                jv_curves_count = sum(1 for line in f if line.strip())
    except Exception:
        pass

    try:
        eqe_spectra_file = out_dir / "eqe_spectra.jsonl"
        if eqe_spectra_file.exists():
            with open(eqe_spectra_file, "r", encoding="utf-8") as f:
                eqe_spectra_count = sum(1 for line in f if line.strip())
    except Exception:
        pass

    try:
        excel_log_file = out_dir / "excel_formula_audit.jsonl"
        if excel_log_file.exists():
            workbook_names = set()
            with open(excel_log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        if "source_file" in d:
                            workbook_names.add(d["source_file"])
            excel_workbooks_count = len(workbook_names)
    except Exception:
        pass

    # Category counts in findings
    jv_rec_count = sum(1 for f in findings if "reconciliation" in f.get("detector_id", "") and "jv" in f.get("source_file", "").lower())
    # Or count by rule_id / detector_id
    jv_rec_count = sum(1 for f in findings if f.get("rule_id") == "pv_source_reconciliation" and "jv" in f.get("finding_id", "").lower())
    eqe_rec_count = sum(1 for f in findings if f.get("rule_id") == "pv_source_reconciliation" and "eqe" in f.get("finding_id", "").lower())
    eqe_jv_mismatch_count = sum(1 for f in findings if f.get("rule_id") == "pv_eqe_spectrum_integration")
    excel_audit_count = sum(1 for f in findings if f.get("rule_id") == "pv_excel_formula_audit")

    # HTML Template
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raw Photovoltaic &amp; Materials Measurement Recalculation Dashboard</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(17, 24, 39, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-blue: #3b82f6;
            --accent-copper: #b48838;
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
            font-family: Aptos, "Noto Sans SC", "Microsoft YaHei", sans-serif;
            line-height: 1.5;
            padding: 2rem;
        }}

        header {{
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-family: Georgia, "Noto Serif SC", "Songti SC", serif;
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #f3f0e8, var(--accent-copper));
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
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
            font-family: Georgia, "Noto Serif SC", "Songti SC", serif;
            font-size: 2.5rem;
            font-weight: 700;
            color: #ffffff;
        }}

        .section-title {{
            font-family: Georgia, "Noto Serif SC", "Songti SC", serif;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
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
            font-family: Georgia, "Noto Serif SC", "Songti SC", serif;
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
            border-left: 3px solid var(--accent-copper);
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
            color: var(--accent-copper);
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
        <h1>Raw PV &amp; Materials Recalculation Dashboard</h1>
        <p style="color: var(--text-muted);">Local review of raw solar measurements and consistency ledger reconciliation</p>
    </header>

    <div class="safety-notice">
        <strong>Safety Notice:</strong> This dashboard reports raw photovoltaic measurement recalculation signals only and does not determine data fabrication or research misconduct.
    </div>

    <section>
        <div class="stats-grid">
            <div class="stat-card">
                <h3>J-V Curves Parsed</h3>
                <p>{jv_curves_count}</p>
            </div>
            <div class="stat-card">
                <h3>EQE Spectra Parsed</h3>
                <p>{eqe_spectra_count}</p>
            </div>
            <div class="stat-card">
                <h3>Excel Workbooks Audited</h3>
                <p>{excel_workbooks_count}</p>
            </div>
            <div class="stat-card">
                <h3>J-V vs Reported Mismatches</h3>
                <p>{jv_rec_count}</p>
            </div>
            <div class="stat-card">
                <h3>EQE vs Reported Mismatches</h3>
                <p>{eqe_rec_count}</p>
            </div>
            <div class="stat-card">
                <h3>EQE vs J-V current Mismatches</h3>
                <p>{eqe_jv_mismatch_count}</p>
            </div>
            <div class="stat-card">
                <h3>Excel Formula Audit findings</h3>
                <p>{excel_audit_count}</p>
            </div>
        </div>
    </section>

    <section>
        <div class="section-title">Consistency &amp; Recalculation Signals ({len(findings)})</div>
        <div class="findings-grid">
        """

    for f in findings:
        fid = _escape(f.get("finding_id", ""))
        rule_id = _escape(f.get("rule_id", ""))
        det_id = _escape(f.get("detector_id", ""))
        risk_value = str(f.get("risk_level", "low"))
        risk = _escape(risk_value)
        dev_id = _escape(f.get("device_id") or "N/A")
        src_file = _escape(f.get("source_file", ""))
        
        obs_str = json.dumps(f.get("observed_values", {}), indent=2)
        recomp_str = json.dumps(f.get("recomputed_values", {}), indent=2)
        tol_str = json.dumps(f.get("tolerance", {}), indent=2) if f.get("tolerance") else "N/A"
        
        safe_lang = _escape(f.get("safe_report_language", ""))
        
        # Build checklist / explanations lists
        alt_exp_html = "".join(f"<li>{_escape(item)}</li>" for item in f.get("alternative_explanations", []))
        fp_risks_html = "".join(f"<li>{_escape(item)}</li>" for item in f.get("false_positive_risks", []))
        m_verif_html = "".join(f"<li>{_escape(item)}</li>" for item in f.get("manual_verification", []))
        limits_html = "".join(f"<li>{_escape(item)}</li>" for item in f.get("limitations", []))

        badge_class = "badge-medium" if risk_value.lower() == "medium" else "badge-low"

        html_content += f"""
            <div class="finding-card">
                <div class="finding-header">
                    <div>
                        <div class="finding-title">{fid}: {rule_id}</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                            Detector: <code>{det_id}</code> | File: <code>{src_file}</code> | Device ID: <strong>{dev_id}</strong>
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
                        <h4>Recomputed Values</h4>
                        <pre><code>{html.escape(recomp_str)}</code></pre>
                    </div>
                    <div class="detail-item">
                        <h4>Tolerance Config</h4>
                        <pre><code>{html.escape(tol_str)}</code></pre>
                    </div>
                </div>

                <div class="details-grid" style="border-top: 1px solid var(--border-color); padding-top: 1rem; margin-top: 0.5rem;">
                    <div class="list-box">
                        <h5>Alternative Benign Explanations</h5>
                        <ul>{alt_exp_html}</ul>
                    </div>
                    <div class="list-box">
                        <h5>False Positive Risks</h5>
                        <ul>{fp_risks_html}</ul>
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

</body>
</html>
"""

    out_file.write_text(html_content, encoding="utf-8")
    print(f"Wrote PV domain dashboard HTML: {display_path(out_file)}")
    return str(out_file)

def main(args=None):
    parsed = parse_args(args)
    run_report_raw_pv_html(parsed.findings_jsonl, parsed.output)

if __name__ == "__main__":
    main()
