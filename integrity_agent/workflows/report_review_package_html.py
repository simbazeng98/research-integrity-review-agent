from __future__ import annotations

import argparse
from pathlib import Path

from integrity_agent.core.path_display import display_path
from integrity_agent.core.reporting import load_jsonl_findings, write_dashboard_html


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Generate unified review package HTML dashboard.")
    parser.add_argument("unified_index", help="Path to unified_evidence_index.jsonl.")
    parser.add_argument(
        "-o",
        "--output",
        default="outputs/review_package/review_package_dashboard.html",
        help="Path to write dashboard HTML.",
    )
    parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Dashboard language.")
    return parser.parse_args(args)


def run_report_review_package_html(
    unified_index: str,
    output_path: str = "outputs/review_package/review_package_dashboard.html",
    locale: str = "en",
) -> str:
    index_path = Path(unified_index)
    findings = load_jsonl_findings(index_path) if index_path.exists() else []
    out_file = write_dashboard_html(findings, Path(output_path), locale=locale)
    print(f"Wrote unified dashboard HTML: {display_path(out_file)}")
    return str(out_file)


def main(args=None):
    parsed = parse_args(args)
    run_report_review_package_html(parsed.unified_index, parsed.output, locale=parsed.lang)


if __name__ == "__main__":
    main()
