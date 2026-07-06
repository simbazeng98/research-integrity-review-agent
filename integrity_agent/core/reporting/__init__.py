"""Report-generation primitives."""

from integrity_agent.core.reporting.html_dashboard import (
    load_jsonl_findings,
    render_dashboard_html,
    write_dashboard_html,
)

__all__ = ["load_jsonl_findings", "render_dashboard_html", "write_dashboard_html"]
