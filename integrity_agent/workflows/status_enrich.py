from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from integrity_agent.core.evidence.ledger_schema import (
    EvidenceLocation,
    EvidenceRecord,
    ManualVerification,
    ReportLanguageGuard,
    RiskSignal,
)
from integrity_agent.core.metadata.crossref_client import (
    CrossrefClientError,
    CrossrefNotFoundError,
    CrossrefRateLimitError,
    fetch_crossref_work,
)
from integrity_agent.core.metadata.doi import normalize_doi

DEFAULT_OUTPUT_DIR = Path("outputs") / "status_enrich"


def normalize_status(raw_type: str) -> str:
    """Normalize raw Crossref update type to one of the target statuses:
    retraction, correction, expression_of_concern, withdrawal, update_notice, or reinstatement.
    """
    t = str(raw_type).strip().lower()
    if "retraction" in t:
        return "retraction"
    elif "withdrawal" in t:
        return "withdrawal"
    elif "concern" in t:
        return "expression_of_concern"
    elif "reinstatement" in t:
        return "reinstatement"
    elif "correction" in t:
        return "correction"
    elif "update" in t or "notice" in t:
        return "update_notice"
    else:
        return "correction"


def _parse_date(date_dict: dict[str, Any] | None) -> str | None:
    if not date_dict or "date-parts" not in date_dict:
        return None
    try:
        parts_list = date_dict["date-parts"]
        if not parts_list or not isinstance(parts_list, list):
            return None
        parts = parts_list[0]
        if not parts or not isinstance(parts, list):
            return None

        valid_parts = [p for p in parts if p is not None]
        if len(valid_parts) >= 3:
            return f"{valid_parts[0]}-{int(valid_parts[1]):02d}-{int(valid_parts[2]):02d}"
        elif len(valid_parts) == 2:
            return f"{valid_parts[0]}-{int(valid_parts[1]):02d}"
        elif len(valid_parts) == 1:
            return f"{valid_parts[0]}"
    except Exception:
        pass
    return None


def parse_doi_status(work_json: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str | None]:
    """Parse updates from work_json and return the overall normalized status,
    the list of normalized update items, and the publication title.
    """
    if not work_json or "message" not in work_json:
        return "metadata_unavailable", [], None

    message = work_json["message"]
    updates = []
    seen_related = set()

    # Extract title
    title = None
    titles = message.get("title", [])
    if titles:
        title = str(titles[0])

    # 1. Parse 'updated-by'
    for item in message.get("updated-by", []):
        raw_type = str(item.get("type", "")).strip().lower()
        if not raw_type:
            continue
        related_doi = str(item.get("DOI", "unknown")).strip().lower()
        if related_doi != "unknown" and related_doi in seen_related:
            continue
        if related_doi != "unknown":
            seen_related.add(related_doi)

        norm_type = normalize_status(raw_type)
        updates.append({
            "type": norm_type,
            "raw_type": raw_type,
            "doi": related_doi,
            "label": item.get("label"),
            "date": _parse_date(item.get("updated")),
            "relation": "updated-by"
        })

    # 2. Parse 'update-to'
    for item in message.get("update-to", []):
        raw_type = str(item.get("type", "")).strip().lower()
        if not raw_type:
            continue
        related_doi = str(item.get("DOI", "unknown")).strip().lower()
        if related_doi != "unknown" and related_doi in seen_related:
            continue
        if related_doi != "unknown":
            seen_related.add(related_doi)

        norm_type = normalize_status(raw_type)
        updates.append({
            "type": norm_type,
            "raw_type": raw_type,
            "doi": related_doi,
            "label": item.get("label"),
            "date": _parse_date(item.get("updated")),
            "relation": "update-to"
        })

    # Determine overall status
    if not updates:
        return "no_known_update", [], title

    types_found = {u["type"] for u in updates}
    if "reinstatement" in types_found:
        overall = "reinstatement"
    elif "retraction" in types_found:
        overall = "retraction"
    elif "withdrawal" in types_found:
        overall = "withdrawal"
    elif "expression_of_concern" in types_found:
        overall = "expression_of_concern"
    elif "correction" in types_found:
        overall = "correction"
    elif "update_notice" in types_found:
        overall = "update_notice"
    else:
        overall = "no_known_update"

    return overall, updates, title


def extract_dois(input_path: Path) -> list[str]:
    ext = input_path.suffix.lower()
    dois = []
    if ext == ".txt":
        content = input_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            val = line.strip()
            if val:
                try:
                    dois.append(normalize_doi(val))
                except ValueError:
                    pass
    elif ext == ".csv":
        from integrity_agent.core.intake.adapters.doi_list import parse_doi_list
        items = parse_doi_list(input_path)
        for item in items:
            if item.normalized_doi:
                dois.append(item.normalized_doi)
    elif ext == ".jsonl":
        content = input_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                doi_val = data.get("normalized_doi") or data.get("doi") or data.get("DOI")
                if doi_val and isinstance(doi_val, str):
                    dois.append(normalize_doi(doi_val))
            except Exception:
                pass
    elif ext == ".json":
        content = input_path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        try:
                            dois.append(normalize_doi(item))
                        except ValueError:
                            pass
                    elif isinstance(item, dict):
                        doi_val = item.get("normalized_doi") or item.get("doi") or item.get("DOI")
                        if doi_val and isinstance(doi_val, str):
                            dois.append(normalize_doi(doi_val))
            elif isinstance(data, dict):
                def recurse_extract(d: Any):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if k.lower() in ("doi", "normalized_doi") and isinstance(v, str):
                                try:
                                    dois.append(normalize_doi(v))
                                except ValueError:
                                    pass
                            else:
                                recurse_extract(v)
                    elif isinstance(d, list):
                        for el in d:
                            recurse_extract(el)
                recurse_extract(data)
        except Exception:
            pass
    else:
        raise ValueError(f"Unsupported input file format: {ext}")

    seen = set()
    deduped = []
    for d in dois:
        if d not in seen:
            seen.add(d)
            deduped.append(d)
    return deduped


def build_evidence_record(
    doi: str,
    status: str,
    title: str | None,
    updates: list[dict[str, Any]],
    source_filename: str,
    lookup_mode: str,
) -> EvidenceRecord:
    # Slugify DOI to create a valid finding_id
    doi_slug = re.sub(r"[^a-zA-Z0-9_]", "_", doi)
    finding_id = f"status_enrich_{doi_slug}"

    # Determine risk level
    if status in ("retraction", "withdrawal"):
        risk = "high"
    elif status == "expression_of_concern":
        risk = "medium"
    else:
        risk = "low"

    # Needs manual review matches risk level
    needs_manual_review = risk in ("high", "medium")

    # Titles
    title_text = {
        "en": f"Publication Status Enrichment: {doi}",
        "zh": f"文献状态富集: {doi}",
    }

    # Summary and safe report language must contain "status context is not proof of misconduct"
    summary_text = {
        "en": f"Publication status for DOI {doi} enriched to '{status}' based on Crossref. Note: publication status context is not proof of misconduct.",
        "zh": f"根据 Crossref，文献 DOI {doi} 状态为 '{status}'。注：状态上下文并非学术不端的证据。",
    }

    safe_report_lang = f"Publication status: {status}. Note: status context is not proof of misconduct."

    # Build evidence locations
    evidence = [
        EvidenceLocation(
            source=f"doi:{doi}",
            location=f"Crossref Metadata for DOI {doi}",
            metadata={
                "title": title or "Unknown",
                "updates_count": len(updates),
                "updates": updates,
            },
        )
    ]

    # Manual verification
    requests = []
    if needs_manual_review:
        requests = [
            {
                "en": f"Verify the status '{status}' notice on the journal website. Note: status context is not proof of misconduct.",
                "zh": f"在期刊网站核实状态 '{status}' 的具体通知。注：状态上下文并非学术不端的证据。",
            }
        ]
    manual_verification = ManualVerification(needed=needs_manual_review, requests=requests)

    # Benign alternatives
    alternative_explanations = [
        {
            "en": "A retraction, withdrawal, or correction does not imply research misconduct. It can result from honest scientific error, author correction, or administrative publisher updates. Status context is not proof of misconduct.",
            "zh": "撤稿、撤回或勘误并不意味着学术不端。它们可能源于诚实的科学错误、作者更正或出版商的行政更新。状态上下文并非学术不端的证据。",
        }
    ]

    # False positive risks
    false_positive_risks = [
        {
            "en": "Crossref update metadata may be misclassified, outdated, or delayed.",
            "zh": "Crossref 更新元数据可能分类错误、陈旧或延迟。",
        }
    ]

    # Limitations
    limitations = [
        {
            "en": "Only Crossref metadata was queried. Independent verification on the publisher website is required. Status context is not proof of misconduct.",
            "zh": "仅查询了 Crossref 元数据。需在出版商网站进行独立核实。状态上下文并非学术不端的证据。",
        }
    ]

    # Report language guard
    report_language_guard = ReportLanguageGuard(
        safe_report_language=safe_report_lang,
        forbidden_verdict_phrases_blocked=True,
        requires_manual_verification_language=True,
    )

    # Risk signal
    risk_signal = RiskSignal(
        risk_level=risk,
        rule_id="status_enrichment",
        workflow_id="status_enrich",
        confidence=1.0,
    )

    return EvidenceRecord(
        finding_id=finding_id,
        finding_category="status_enrichment",
        type="status_enrichment",
        title=title_text,
        summary=summary_text,
        risk=risk,
        risk_level=risk,
        needs_manual_review=needs_manual_review,
        evidence=evidence,
        manual_verification=manual_verification,
        false_positive_risks=false_positive_risks,
        alternative_explanations=alternative_explanations,
        limitations=limitations,
        provenance={
            "source": "Crossref Works API",
            "doi": doi,
            "lookup_mode": lookup_mode,
            "source_filename": source_filename,
            "raw_status": status,
            "status_relations": updates,
        },
        rule_id="status_enrichment",
        safe_report_language=safe_report_lang,
        risk_signal=risk_signal,
        report_language_guard=report_language_guard,
    )


def generate_status_summary_md(
    output_path: Path,
    input_file_name: str,
    lookup_mode: str,
    records: list[EvidenceRecord],
    errors_count: int,
) -> None:
    total = len(records)

    # Calculate counts
    status_counts: dict[str, int] = {}
    for r in records:
        status = r.provenance.get("raw_status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    lines = [
        "# Publication Status Enrichment Summary",
        "",
        "## Run Configuration",
        f"- **Input file**: `{input_file_name}`",
        f"- **Lookup mode**: `{lookup_mode}`",
        f"- **Total DOIs processed**: {total}",
        f"- **Errors/Failures**: {errors_count}",
        "",
        "## Status Summary Breakdown",
    ]

    for status, count in sorted(status_counts.items()):
        lines.append(f"- **{status}**: {count}")

    lines.extend([
        "",
        "## Safety Notice",
        "> [not_proof_of_misconduct_alert]",
        "> **Publication status context is not proof of misconduct.**",
        "> A correction, update notice, expression of concern, withdrawal, or retraction does not imply research misconduct. Such updates may be due to honest errors, author self-corrections, or administrative issues.",
        "",
        "## Enriched Items Ledger",
        "",
        "| DOI | Title | Normalized Status | Risk Level | Needs Manual Review |",
        "| --- | ----- | ----------------- | ---------- | ------------------- |",
    ])

    for r in records:
        doi = r.provenance.get("doi", "unknown")
        status = r.provenance.get("raw_status", "unknown")
        title = r.evidence[0].metadata.get("title", "Unknown") if r.evidence else "Unknown"
        risk = r.risk
        needs_review = "Yes" if r.needs_manual_review else "No"
        lines.append(f"| `{doi}` | {title} | `{status}` | `{risk}` | {needs_review} |")

    lines.extend([
        "",
        "## Limitations",
        "- Status enrichment relies strictly on automated queries to the Crossref API.",
        "- Crossref metadata updates may experience indexing delays or latency.",
        "- A status of `no_known_update` does not guarantee a paper has no issues.",
        "- A status of `metadata_unavailable` does not imply any issue with the paper.",
        "",
    ])

    # Convert the custom alert syntax placeholder to GitHub Flavored Markdown blockquotes
    content = "\n".join(lines).replace("[not_proof_of_misconduct_alert]", "!IMPORTANT")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def run_status_enrich(
    input_path: Path | str,
    allow_network: bool = False,
    mailto: str | None = None,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path]:
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # 1. Extract DOIs
    dois = extract_dois(input_path)
    lookup_mode = "allow-network" if allow_network else "offline"

    records = []
    errors_count = 0

    # 2. Process each DOI
    for doi in dois:
        try:
            work_json = fetch_crossref_work(
                doi,
                allow_network=allow_network,
                mailto=mailto,
            )
            overall_status, updates, title = parse_doi_status(work_json)
        except CrossrefNotFoundError:
            overall_status, updates, title = "metadata_unavailable", [], None
            errors_count += 1
        except CrossrefRateLimitError:
            overall_status, updates, title = "metadata_unavailable", [], None
            errors_count += 1
        except CrossrefClientError:
            overall_status, updates, title = "metadata_unavailable", [], None
            errors_count += 1
        except Exception:
            overall_status, updates, title = "metadata_unavailable", [], None
            errors_count += 1

        record = build_evidence_record(
            doi=doi,
            status=overall_status,
            title=title,
            updates=updates,
            source_filename=input_path.name,
            lookup_mode=lookup_mode,
        )
        records.append(record)

    # 3. Write outputs
    if output_dir is None:
        resolved_out_dir = DEFAULT_OUTPUT_DIR
    else:
        resolved_out_dir = Path(output_dir)

    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = resolved_out_dir / "status_items.jsonl"
    summary_path = resolved_out_dir / "status_summary.md"

    # Write JSONL
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json(by_alias=True) + "\n")

    # Write summary markdown
    generate_status_summary_md(
        summary_path,
        input_file_name=input_path.name,
        lookup_mode=lookup_mode,
        records=records,
        errors_count=errors_count,
    )

    return jsonl_path.resolve(), summary_path.resolve()
