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
from integrity_agent.core.evidence.scope import split_public_records
from integrity_agent.core.risk_model import calculate_mrpi
from integrity_agent.core.safety import find_runtime_safety_issues


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


def _record_value(record: dict[str, Any], key: str) -> Any:
    for container in (
        record,
        record.get("provenance"),
        record.get("metadata"),
    ):
        if isinstance(container, dict) and container.get(key) not in (None, ""):
            return container[key]
    return None


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
        "evidence_tier": str(_record_value(record, "evidence_tier") or ""),
        "source_version": str(_record_value(record, "source_version") or ""),
        "resolution_status": str(
            _record_value(record, "resolution_status") or ""
        ),
        "counter_evidence": _record_value(record, "counter_evidence") or [],
        "do_not_overclaim": str(
            _record_value(record, "do_not_overclaim") or ""
        ),
        "mechanism_interpretation": str(
            _record_value(record, "mechanism_interpretation")
            or "No mechanism, intent, or responsibility is inferred from this signal."
        ),
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


def _counter_evidence_html(value: Any) -> str:
    if not value:
        return "None recorded."
    items = value if isinstance(value, list) else [value]
    rendered: list[str] = []
    for item in items:
        if isinstance(item, dict):
            parts = [
                f"{key}={item[key]}"
                for key in (
                    "event_id",
                    "source_type",
                    "source_version",
                    "source_url",
                )
                if item.get(key)
            ]
            rendered.append(", ".join(parts) or json.dumps(item, ensure_ascii=False))
        else:
            rendered.append(str(item))
    return "; ".join(rendered)


def _structured_context_html(record: dict[str, Any]) -> str:
    if not any(
        record.get(key)
        for key in (
            "evidence_tier",
            "source_version",
            "resolution_status",
            "counter_evidence",
            "do_not_overclaim",
        )
    ):
        return ""
    verification = record["manual_verification"]["en"]
    verification_text = verification[0] if verification else "None recorded."
    source_fact = "None recorded."
    if record["evidence"] and isinstance(record["evidence"][0], dict):
        item = record["evidence"][0]
        source = item.get("source") or item.get("relative_path") or "unknown"
        location = item.get("location") or ""
        source_fact = f"{source} at {location}".strip()
    rows = [
        ("Source fact", source_fact),
        ("Detector/recomputation result", record["summary"]["en"]),
        ("Mechanism interpretation", record["mechanism_interpretation"]),
        ("Transferability/verification request", verification_text),
        ("Evidence tier", record["evidence_tier"] or "Not assigned."),
        ("Source version", record["source_version"] or "Not recorded."),
        ("Resolution status", record["resolution_status"] or "open"),
        ("Counter-evidence", _counter_evidence_html(record["counter_evidence"])),
        (
            "Do-not-overclaim",
            record["do_not_overclaim"]
            or "Treat as a candidate signal requiring human review.",
        ),
    ]
    return (
        '<section class="box structured-review-context"><h3>Structured review context</h3><ul>'
        + "".join(
            f"<li><strong>{html.escape(label)}:</strong> {html.escape(str(value))}</li>"
            for label, value in rows
        )
        + "</ul></section>"
    )


STATUS_ZH_MAP = {
    "correction": "修正/勘误 (Correction)",
    "retraction": "撤稿 (Retraction)",
    "expression_of_concern": "关注声明 (Expression of Concern)",
    "withdrawal": "撤回 (Withdrawal)",
    "update": "更新 (Update)",
}


def render_dashboard_html(
    findings: Iterable[Finding | dict[str, Any]],
    locale: str = "en",
) -> str:
    # Materialize findings to list to prevent generator exhaustion
    findings = list(findings)
    safety_payload = [
        finding.to_ledger_record() if isinstance(finding, Finding) else finding
        for finding in findings
    ]
    safety_issues = find_runtime_safety_issues(safety_payload)
    if safety_issues:
        raise ValueError(
            "unsafe dashboard finding content: "
            + "; ".join(sorted(set(safety_issues)))
        )
    findings, engineering_findings = split_public_records(findings)

    # Separate findings
    status_findings = []
    reference_findings = []
    pv_completeness_findings = []
    normal_findings = []

    # We want to build normalisation/stats over all findings first,
    # to keep total counts and MRPI accurate for all findings.
    normalized_all = [_normalise_record(finding) for finding in findings]
    risk_counts = {
        "high": sum(1 for finding in normalized_all if finding["risk_level"] == "high"),
        "medium": sum(1 for finding in normalized_all if finding["risk_level"] == "medium"),
        "low": sum(1 for finding in normalized_all if finding["risk_level"] == "low"),
    }
    # Preserve provenance, scope, resolution, and correlation metadata for MRPI.
    # The normalized display records intentionally omit several scoring fields.
    mrpi = calculate_mrpi(findings)

    # Now, physically separate the records for HTML display
    for finding in findings:
        category = ""
        if hasattr(finding, "finding_category"):
            category = finding.finding_category
        elif isinstance(finding, dict):
            category = finding.get("finding_category") or finding.get("type")

        if category == "status_enrichment":
            status_findings.append(finding)
        elif category == "reference_anomaly":
            reference_findings.append(finding)
        elif category == "pv_evidence_completeness":
            pv_completeness_findings.append(finding)
        else:
            normal_findings.append(finding)

    # Render normal cards
    normalized_normal = [_normalise_record(finding) for finding in normal_findings]
    cards = []
    for finding in normalized_normal:
        cards.append(
            f"""
      <article data-finding-card data-risk="{finding["risk_level"]}">
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
          {_structured_context_html(finding)}
        </div>
      </article>"""
        )

    engineering_cards = []
    for question in (_normalise_record(item) for item in engineering_findings):
        engineering_cards.append(
            f"""
      <article data-finding-card data-risk="outside-score" class="engineering-plausibility-question">
        <div class="finding-head">
          <div>
            <h2>{_lang_span(question["title"])}</h2>
            <div class="meta"><code>{html.escape(question["finding_id"])}</code> | <code>{html.escape(question["rule_id"])}</code></div>
          </div>
        </div>
        <div class="summary">{_lang_span(question["summary"])}</div>
        <div class="grid">
          <section class="box"><h3><span data-lang="en">Supplied context</span><span data-lang="zh">已提供上下文</span></h3>{_evidence_html(question["evidence"])}</section>
          <section class="box"><h3><span data-lang="en">Engineering verification requests</span><span data-lang="zh">工程可行性复核请求</span></h3>{_list_html(question["manual_verification"])}</section>
        </div>
      </article>"""
        )
    engineering_html = ""
    if engineering_cards:
        engineering_html = f"""
    <section class="engineering-plausibility" data-review-section style="margin-bottom: 24px;">
      <h2>
        <span data-lang="en">Engineering Plausibility Questions (Outside Integrity MRPI)</span>
        <span data-lang="zh">工程可行性问题（不计入研究诚信 MRPI）</span>
      </h2>
      {''.join(engineering_cards)}
    </section>"""

    # Render status enrichment cards
    status_cards = []
    for f in status_findings:
        record = f.to_ledger_record() if hasattr(f, "to_ledger_record") else dict(f)
        provenance = record.get("provenance") or {}
        doi = html.escape(str(provenance.get("doi") or "Unknown DOI"))
        raw_status = html.escape(str(provenance.get("raw_status") or "unknown"))
        status_zh = STATUS_ZH_MAP.get(raw_status.lower(), raw_status)
        risk_level = str(record.get("risk_level", record.get("risk", "low"))).lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = "low"

        # Relations: updates list
        relations = provenance.get("status_relations") or []
        updates_list_en = []
        updates_list_zh = []
        if not relations:
            updates_html = (
                '<ul data-lang="en"><li>No related updates recorded.</li></ul>'
                '<ul data-lang="zh"><li>未记录关联更新。</li></ul>'
            )
        else:
            for rel in relations:
                rel_doi = html.escape(str(rel.get("doi") or ""))
                rel_type = html.escape(str(rel.get("type") or ""))
                rel_date = html.escape(str(rel.get("date") or ""))
                rel_relation = html.escape(str(rel.get("relation") or ""))

                updates_list_en.append(
                    f'<div style="margin-bottom: 8px; border-bottom: 1px dashed var(--line); padding-bottom: 6px;">'
                    f'<div><strong>Related Update DOI:</strong> <code>{rel_doi}</code></div>'
                    f'<div><strong>Update Type:</strong> <code>{rel_type}</code></div>'
                    f'<div><strong>Relation:</strong> <code>{rel_relation}</code></div>'
                    f'<div><strong>Update Date:</strong> <code>{rel_date}</code></div>'
                    f'</div>'
                )
                updates_list_zh.append(
                    f'<div style="margin-bottom: 8px; border-bottom: 1px dashed var(--line); padding-bottom: 6px;">'
                    f'<div><strong>关联更新 DOI:</strong> <code>{rel_doi}</code></div>'
                    f'<div><strong>更新类型:</strong> <code>{rel_type}</code></div>'
                    f'<div><strong>关联关系:</strong> <code>{rel_relation}</code></div>'
                    f'<div><strong>更新日期:</strong> <code>{rel_date}</code></div>'
                    f'</div>'
                )
            updates_html = (
                f'<div data-lang="en">{"".join(updates_list_en)}</div>'
                f'<div data-lang="zh">{"".join(updates_list_zh)}</div>'
            )

        # Safe report language
        safe_lang = record.get("safe_report_language") or record.get("summary") or ""
        if isinstance(safe_lang, dict):
            safe_report_lang_en = html.escape(resolve_bilingual_string(safe_lang, "en"))
            safe_report_lang_zh = html.escape(resolve_bilingual_string(safe_lang, "zh"))
        else:
            safe_report_lang_en = html.escape(str(safe_lang))
            safe_report_lang_zh = html.escape(str(safe_lang))

        # Manual verification requests
        mv_val = record.get("manual_verification")
        if isinstance(mv_val, dict):
            mv_requests = mv_val.get("requests") or []
        else:
            mv_requests = mv_val or []

        mv_pair = _list_pair(mv_requests)
        if not mv_pair["en"]:
            mv_pair["en"] = [f"Verify the status '{raw_status}' notice on the journal website. Note: status context is not proof of misconduct."]
        if not mv_pair["zh"]:
            mv_pair["zh"] = [f"在期刊网站核实状态 '{raw_status}' 的具体通知。注：状态上下文并非学术不端的证据。"]

        mv_html = _list_html(mv_pair)

        # Construct status enrichment card
        status_cards.append(
            f"""
      <article data-finding-card data-risk="{risk_level}" class="status-enrichment-card" style="border: 2px solid var(--blue); background: var(--panel);">
        <div class="finding-head">
          <div>
            <h2>
              <span data-lang="en">Publication Status Context</span>
              <span data-lang="zh">文献出版状态上下文</span>
            </h2>
            <div class="meta"><strong>DOI:</strong> <code>{doi}</code></div>
          </div>
          <span class="badge risk-{risk_level}">{risk_level}</span>
        </div>

        <div class="summary" style="border-left-color: var(--blue); background: #f0f5ff; margin-bottom: 12px; padding: 10px 12px; border-radius: 0 8px 8px 0;">
          <span data-lang="en">Status: <strong>{raw_status}</strong></span>
          <span data-lang="zh">文献状态: <strong>{status_zh}</strong></span>
        </div>

        <div style="background: #f0fdf4; border-left: 4px solid var(--green); padding: 10px 12px; border-radius: 0 8px 8px 0; margin-bottom: 12px;">
          <div style="font-weight: bold; color: var(--green); margin-bottom: 4px; font-size: 0.9rem;">
            <span data-lang="en">Safe Report Language (Candidate Context)</span>
            <span data-lang="zh">安全报告文本 (候选上下文)</span>
          </div>
          <div style="font-size: 0.95rem;">
            <span data-lang="en">{safe_report_lang_en}</span>
            <span data-lang="zh">{safe_report_lang_zh}</span>
          </div>
        </div>

        <div style="border: 1px solid #f1c27d; background: #fff7ed; color: #7c2d12; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 0.88rem; font-weight: bold;">
          <span data-lang="en"><strong>Notice:</strong> Publication status context is not proof of research misconduct. It is a candidate context that needs manual verification.</span>
          <span data-lang="zh"><strong>提示:</strong> 文献出版状态上下文并非学术不端的证据。这属于需要人工核实确认的候选上下文。</span>
        </div>

        <div class="grid">
          <section class="box">
            <h3>
              <span data-lang="en">Related Update Notices</span>
              <span data-lang="zh">关联更新通知</span>
            </h3>
            {updates_html}
          </section>

          <section class="box">
            <h3>
              <span data-lang="en">Manual Verification Requests</span>
              <span data-lang="zh">人工复核请求</span>
            </h3>
            {mv_html}
          </section>
        </div>
      </article>"""
        )

    if status_cards:
        status_enrichment_html = f"""
    <section data-review-section style="margin-top: 18px; margin-bottom: 24px;">
      <h2 style="font-size: 1.3rem; margin-bottom: 12px; border-bottom: 2px solid var(--line); padding-bottom: 6px;">
        <span data-lang="en">Publication Status / Status Enrichment</span>
        <span data-lang="zh">文献出版状态 / 状态富集</span>
      </h2>
      <div style="display: grid; gap: 12px;">
        {"".join(status_cards)}
      </div>
    </section>"""
    else:
        status_enrichment_html = ""

    # Render reference anomalies
    reference_cards = []
    for f in reference_findings:
        record = f.to_ledger_record() if hasattr(f, "to_ledger_record") else dict(f)
        provenance = record.get("provenance") or {}

        rule_id = html.escape(str(record.get("rule_id") or record.get("type") or "unknown_rule"))
        risk_level = str(record.get("risk_level", record.get("risk", "low"))).lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = "low"

        finding_id = html.escape(str(record.get("finding_id") or "FINDING"))

        evidence = record.get("evidence") or record.get("evidence_items") or []
        evidence_loc_str = ""
        if evidence:
            ev = evidence[0]
            if isinstance(ev, dict):
                loc = ev.get("location") or ""
                src = ev.get("source") or ""
                evidence_loc_str = f"{src} | {loc}" if src else loc
            else:
                evidence_loc_str = str(ev)
        evidence_loc_str = html.escape(evidence_loc_str)

        target_id = html.escape(str(
            provenance.get("doi")
            or provenance.get("raw_doi")
            or provenance.get("duplicate_item")
            or "N/A"
        ))

        # Safe report language
        safe_lang = record.get("safe_report_language") or record.get("summary") or ""
        if isinstance(safe_lang, dict):
            safe_report_lang_en = html.escape(resolve_bilingual_string(safe_lang, "en"))
            safe_report_lang_zh = html.escape(resolve_bilingual_string(safe_lang, "zh"))
        else:
            safe_report_lang_en = html.escape(str(safe_lang))
            safe_report_lang_zh = html.escape(str(safe_lang))

        # Manual verification requests
        mv_val = record.get("manual_verification")
        if isinstance(mv_val, dict):
            mv_requests = mv_val.get("requests") or []
        else:
            mv_requests = mv_val or []
        mv_pair = _list_pair(mv_requests)
        mv_html = _list_html(mv_pair)

        reference_cards.append(
            f"""
      <article data-finding-card data-risk="{risk_level}" class="reference-anomaly-card" style="border: 2px solid var(--amber); background: var(--panel); margin-bottom: 12px;">
        <div class="finding-head">
          <div>
            <h2>
              <span data-lang="en">Bibliographic / Reference Anomaly</span>
              <span data-lang="zh">文献引用异常</span>
            </h2>
            <div class="meta">
              <code>{finding_id}</code> | <strong>Rule:</strong> <code>{rule_id}</code> | <strong>Location:</strong> <code>{evidence_loc_str}</code>
            </div>
          </div>
          <span class="badge risk-{risk_level}">{risk_level}</span>
        </div>

        <div class="summary" style="border-left-color: var(--amber); background: #fffbeb; margin-bottom: 12px; padding: 10px 12px; border-radius: 0 8px 8px 0;">
          <span data-lang="en"><strong>Target Identifier:</strong> <code>{target_id}</code></span>
          <span data-lang="zh"><strong>目标标识符:</strong> <code>{target_id}</code></span>
        </div>

        <div style="background: #f0fdf4; border-left: 4px solid var(--green); padding: 10px 12px; border-radius: 0 8px 8px 0; margin-bottom: 12px;">
          <div style="font-weight: bold; color: var(--green); margin-bottom: 4px; font-size: 0.9rem;">
            <span data-lang="en">Safe Report Language (Candidate Bibliographic Signal)</span>
            <span data-lang="zh">安全报告文本 (候选文献计量信号)</span>
          </div>
          <div style="font-size: 0.95rem;">
            <span data-lang="en">{safe_report_lang_en}</span>
            <span data-lang="zh">{safe_report_lang_zh}</span>
          </div>
        </div>

        <div style="border: 1px solid #f1c27d; background: #fff7ed; color: #7c2d12; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 0.88rem; font-weight: bold;">
          <span data-lang="en"><strong>Notice:</strong> Bibliographic reference anomalies are bibliographic integrity fingerprints and are not proof of research misconduct. They represent candidate signals requiring manual verification.</span>
          <span data-lang="zh"><strong>提示:</strong> 文献引用异常属于文献计量学完整性指纹，并非学术不端的证据。这属于需要人工核实确认的候选信号。</span>
        </div>

        <div class="grid">
          <section class="box" style="grid-column: 1 / -1;">
            <h3>
              <span data-lang="en">Manual Verification Requests</span>
              <span data-lang="zh">人工复核请求</span>
            </h3>
            {mv_html}
          </section>
        </div>
      </article>"""
        )

    # Render PV Evidence Completeness Section
    pv_cards = []
    for f in pv_completeness_findings:
        record = f.to_ledger_record() if hasattr(f, "to_ledger_record") else dict(f)
        provenance = record.get("provenance") or {}

        rule_id = html.escape(str(record.get("rule_id") or record.get("type") or "unknown_rule"))
        risk_level = str(record.get("risk_level", record.get("risk", "low"))).lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = "low"

        finding_id = html.escape(str(record.get("finding_id") or "FINDING"))

        evidence = record.get("evidence") or record.get("evidence_items") or []
        evidence_loc_str = ""
        if evidence:
            ev = evidence[0]
            if isinstance(ev, dict):
                loc = ev.get("location") or ""
                src = ev.get("source") or ""
                evidence_loc_str = f"{src} | {loc}" if src else loc
            else:
                evidence_loc_str = str(ev)
        evidence_loc_str = html.escape(evidence_loc_str)

        missing_fields = ", ".join(provenance.get("missing_fields") or [])
        missing_fields = html.escape(missing_fields) if missing_fields else "N/A"

        # Title and Summary
        safe_lang = record.get("safe_report_language") or record.get("summary") or ""
        if isinstance(safe_lang, dict):
            safe_report_lang_en = html.escape(resolve_bilingual_string(safe_lang, "en"))
            safe_report_lang_zh = html.escape(resolve_bilingual_string(safe_lang, "zh"))
        else:
            safe_report_lang_en = html.escape(str(safe_lang))
            safe_report_lang_zh = html.escape(str(safe_lang))

        # Manual verification requests
        mv_val = record.get("manual_verification")
        if isinstance(mv_val, dict):
            mv_requests = mv_val.get("requests") or []
        else:
            mv_requests = mv_val or []
        mv_pair = _list_pair(mv_requests)
        mv_html = _list_html(mv_pair)

        pv_cards.append(
            f"""
      <article data-finding-card data-risk="{risk_level}" class="pv-completeness-card" style="border: 2px solid var(--emerald, #2e6a55); background: var(--panel); margin-bottom: 12px;">
        <div class="finding-head">
          <div>
            <h2>
              <span data-lang="en">PV Evidence Completeness Gap</span>
              <span data-lang="zh">PV 证据完整性缺失</span>
            </h2>
            <div class="meta">
              <code>{finding_id}</code> | <strong>Rule:</strong> <code>{rule_id}</code> | <strong>Location:</strong> <code>{evidence_loc_str}</code>
            </div>
          </div>
          <span class="badge risk-{risk_level}">{risk_level}</span>
        </div>

        <div class="summary" style="border-left-color: var(--emerald, #10b981); background: #ecfdf5; margin-bottom: 12px; padding: 10px 12px; border-radius: 0 8px 8px 0;">
          <span data-lang="en"><strong>Missing Fields:</strong> <code>{missing_fields}</code></span>
          <span data-lang="zh"><strong>缺失字段:</strong> <code>{missing_fields}</code></span>
        </div>

        <div style="background: #f0fdf4; border-left: 4px solid var(--green); padding: 10px 12px; border-radius: 0 8px 8px 0; margin-bottom: 12px;">
          <div style="font-weight: bold; color: var(--green); margin-bottom: 4px; font-size: 0.9rem;">
            <span data-lang="en">Safe Report Language (Candidate Completeness Signal)</span>
            <span data-lang="zh">安全报告文本 (候选完整性信号)</span>
          </div>
          <div style="font-size: 0.95rem;">
            <span data-lang="en">{safe_report_lang_en}</span>
            <span data-lang="zh">{safe_report_lang_zh}</span>
          </div>
        </div>

        <div style="border: 1px solid #f1c27d; background: #fff7ed; color: #7c2d12; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 0.88rem; font-weight: bold;">
          <span data-lang="en"><strong>Notice:</strong> This is a taxonomy/advisory completeness signal, not an automatic misconduct detector. It requires source/raw data review to determine validity.</span>
          <span data-lang="zh"><strong>提示:</strong> 本项属于分类/建议性完整性信号，并非自动学术不端检测工具。这需要结合原始/源数据审查进行人工核实。</span>
        </div>

        <div class="grid">
          <section class="box" style="grid-column: 1 / -1;">
            <h3>
              <span data-lang="en">Manual Verification Requests</span>
              <span data-lang="zh">人工复核请求</span>
            </h3>
            {mv_html}
          </section>
        </div>
      </article>"""
        )

    if pv_cards:
        pv_completeness_html = f"""
    <section data-review-section style="margin-top: 18px; margin-bottom: 24px;">
      <h2 style="font-size: 1.3rem; margin-bottom: 12px; border-bottom: 2px solid var(--emerald, #10b981); padding-bottom: 6px;">
        <span data-lang="en">PV Evidence Completeness Reviews</span>
        <span data-lang="zh">光伏组件及材料报告完整性评估</span>
      </h2>
      <div style="display: grid; gap: 12px;">
        {"".join(pv_cards)}
      </div>
    </section>"""
    else:
        pv_completeness_html = ""

    if reference_cards:
        reference_anomalies_html = f"""
    <section data-review-section style="margin-top: 18px; margin-bottom: 24px;">
      <h2 style="font-size: 1.3rem; margin-bottom: 12px; border-bottom: 2px solid var(--line); padding-bottom: 6px;">
        <span data-lang="en">Reference / Bibliography Anomalies</span>
        <span data-lang="zh">文献引用异常检测</span>
      </h2>
      <div style="display: grid; gap: 12px;">
        {"".join(reference_cards)}
      </div>
    </section>"""
    else:
        reference_anomalies_html = ""

    safe_locale = "zh" if locale == "zh" else "en"
    mrpi_text = f"{mrpi:.2f}".rstrip("0").rstrip(".")
    findings_html = "\n".join(cards) if cards else "<article>No findings recorded.</article>"
    findings_html = engineering_html + findings_html
    return (
        TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("__DEFAULT_LOCALE__", safe_locale)
        .replace("__EN_ACTIVE__", "true" if safe_locale == "en" else "false")
        .replace("__ZH_ACTIVE__", "true" if safe_locale == "zh" else "false")
        .replace("__MRPI__", mrpi_text)
        .replace("__MRPI_WIDTH__", str(min(100.0, max(0.0, mrpi))))
        .replace("__TOTAL_FINDINGS__", str(len(normalized_all)))
        .replace("__RISK_COUNTS__", f"{risk_counts['high']} / {risk_counts['medium']} / {risk_counts['low']}")
        .replace("__STATUS_ENRICHMENT_HTML__", status_enrichment_html)
        .replace("__REFERENCE_ANOMALIES_HTML__", reference_anomalies_html)
        .replace("__PV_COMPLETENESS_HTML__", pv_completeness_html)
        .replace("__FINDINGS_HTML__", findings_html)
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
