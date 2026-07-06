from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Iterable

from integrity_agent.core.evidence.schema import (
    Finding,
    resolve_bilingual_list,
    resolve_bilingual_string,
)
from integrity_agent.core.risk_model import calculate_mrpi


TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"


def load_jsonl_findings(path: Path | str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                findings.append(json.loads(line))
    return findings


def _pair(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "en": resolve_bilingual_string(value, "en"),
            "zh": resolve_bilingual_string(value, "zh"),
        }
    text = "" if value is None else str(value)
    return {"en": text, "zh": text}


def _list_pair(value: Any) -> dict[str, list[str]]:
    if isinstance(value, dict):
        return {
            "en": [resolve_bilingual_string(value, "en")],
            "zh": [resolve_bilingual_string(value, "zh")],
        }
    if not isinstance(value, list):
        return {"en": [], "zh": []}
    return {
        "en": resolve_bilingual_list(value, "en"),
        "zh": resolve_bilingual_list(value, "zh"),
    }


def _normalise_record(finding: Finding | dict[str, Any]) -> dict[str, Any]:
    record = finding.to_ledger_record() if isinstance(finding, Finding) else dict(finding)
    risk = str(record.get("risk_level", record.get("risk", "low"))).lower()
    if risk not in {"low", "medium", "high"}:
        risk = "low"
    manual_value = record.get("manual_verification")
    if isinstance(manual_value, dict):
        manual_value = manual_value.get("requests", [])
    return {
        "finding_id": str(record.get("finding_id") or record.get("item_id") or "FINDING"),
        "rule_id": str(record.get("rule_id") or record.get("type") or "unknown_rule"),
        "risk_level": risk,
        "title": _pair(record.get("title") or record.get("rule_id") or record.get("type") or "finding"),
        "summary": _pair(
            record.get("safe_report_language")
            or record.get("summary")
            or record.get("risk_signal")
            or ""
        ),
        "evidence": record.get("evidence") or record.get("evidence_items") or [],
        "alternative_explanations": _list_pair(record.get("alternative_explanations", [])),
        "manual_verification": _list_pair(manual_value or []),
        "limitations": _list_pair(record.get("limitations", [])),
    }


def _lang_span(pair: dict[str, str]) -> str:
    return (
        f'<span data-lang="en">{html.escape(pair["en"])}</span>'
        f'<span data-lang="zh">{html.escape(pair["zh"])}</span>'
    )


def _list_html(values: dict[str, list[str]]) -> str:
    en_items = "".join(f"<li>{html.escape(item)}</li>" for item in values["en"]) or "<li>None recorded.</li>"
    zh_items = "".join(f"<li>{html.escape(item)}</li>" for item in values["zh"]) or "<li>未记录。</li>"
    return f'<ul data-lang="en">{en_items}</ul><ul data-lang="zh">{zh_items}</ul>'


def _evidence_html(items: list[Any]) -> str:
    if not items:
        return '<ul><li><span data-lang="en">None recorded.</span><span data-lang="zh">未记录。</span></li></ul>'
    lines = []
    for item in items:
        if isinstance(item, dict):
            source = item.get("source") or item.get("relative_path") or item.get("path") or "unknown"
            location = item.get("location") or item.get("image_id") or item.get("row") or ""
            suffix = f" at {location}" if location else ""
            lines.append(f"<li><code>{html.escape(str(source))}</code>{html.escape(suffix)}</li>")
        else:
            lines.append(f"<li>{html.escape(str(item))}</li>")
    return "<ul>" + "".join(lines) + "</ul>"


def render_dashboard_html(
    findings: Iterable[Finding | dict[str, Any]],
    locale: str = "en",
) -> str:
    normalized = [_normalise_record(finding) for finding in findings]
    risk_counts = {
        "high": sum(1 for finding in normalized if finding["risk_level"] == "high"),
        "medium": sum(1 for finding in normalized if finding["risk_level"] == "medium"),
        "low": sum(1 for finding in normalized if finding["risk_level"] == "low"),
    }
    mrpi = calculate_mrpi(normalized)

    cards = []
    for finding in normalized:
        cards.append(
            f"""
      <article>
        <div class="finding-head">
          <div>
            <h2>{_lang_span(finding["title"])}</h2>
            <div class="meta"><code>{html.escape(finding["finding_id"])}</code> | <code>{html.escape(finding["rule_id"])}</code></div>
          </div>
          <span class="badge risk-{finding["risk_level"]}">{html.escape(finding["risk_level"])}</span>
        </div>
        <div class="summary">{_lang_span(finding["summary"])}</div>
        <div class="grid">
          <section class="box"><h3><span data-lang="en">Evidence</span><span data-lang="zh">证据位置</span></h3>{_evidence_html(finding["evidence"])}</section>
          <section class="box"><h3><span data-lang="en">Alternative benign explanations</span><span data-lang="zh">可能的良性解释</span></h3>{_list_html(finding["alternative_explanations"])}</section>
          <section class="box"><h3><span data-lang="en">Manual verification requests</span><span data-lang="zh">人工复核请求</span></h3>{_list_html(finding["manual_verification"])}</section>
          <section class="box"><h3><span data-lang="en">Limitations</span><span data-lang="zh">局限性</span></h3>{_list_html(finding["limitations"])}</section>
        </div>
      </article>"""
        )

    safe_locale = "zh" if locale == "zh" else "en"
    mrpi_text = f"{mrpi:.2f}".rstrip("0").rstrip(".")
    return (
        TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("__DEFAULT_LOCALE__", safe_locale)
        .replace("__MRPI__", mrpi_text)
        .replace("__MRPI_WIDTH__", str(min(100.0, max(0.0, mrpi))))
        .replace("__TOTAL_FINDINGS__", str(len(normalized)))
        .replace("__RISK_COUNTS__", f"{risk_counts['high']} / {risk_counts['medium']} / {risk_counts['low']}")
        .replace("__FINDINGS_HTML__", "\n".join(cards) if cards else "<article>No findings recorded.</article>")
    )


def write_dashboard_html(
    findings: Iterable[Finding | dict[str, Any]],
    output_path: Path | str,
    locale: str = "en",
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_dashboard_html(findings, locale=locale), encoding="utf-8")
    return out_path.resolve()
