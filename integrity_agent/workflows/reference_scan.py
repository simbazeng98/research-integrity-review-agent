from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Iterable

from integrity_agent.core.evidence.ledger_schema import (
    EvidenceLocation,
    EvidenceRecord,
    ManualVerification,
    ReportLanguageGuard,
    RiskSignal,
)
from integrity_agent.core.metadata.crossref_client import fetch_crossref_work
from integrity_agent.core.metadata.doi import normalize_doi
from integrity_agent.workflows.status_enrich import parse_doi_status

DEFAULT_OUTPUT_DIR = Path("outputs") / "reference_scan"

STATUS_ZH_MAP = {
    "correction": "修正/勘误 (Correction)",
    "retraction": "撤稿 (Retraction)",
    "expression_of_concern": "关注声明 (Expression of Concern)",
    "withdrawal": "撤回 (Withdrawal)",
    "update": "更新 (Update)",
}


def extract_doi_candidates(text: str) -> list[str]:
    candidates = []
    # Find any substring starting with 10.
    matches = re.findall(r"(10\.[^\s,;\"]+)", text)
    for m in matches:
        # Strip common trailing and leading punctuation
        m = re.sub(r"[.,;:)\]]+$", "", m)
        m = re.sub(r"^[(\[]+", "", m)
        candidates.append(m)
    return candidates


def extract_references(input_path: Path) -> list[dict[str, Any]]:
    ext = input_path.suffix.lower()
    references = []

    if ext == ".jsonl":
        with open(input_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Extract the reference string or direct DOI key
                    ref_text = (
                        data.get("reference")
                        or data.get("text")
                        or data.get("ref")
                        or data.get("citation")
                        or data.get("string")
                        or ""
                    )
                    doi_val = (
                        data.get("doi")
                        or data.get("DOI")
                        or data.get("normalized_doi")
                        or ""
                    )

                    references.append({
                        "index": idx,
                        "line_number": idx,
                        "text": str(ref_text).strip(),
                        "doi": str(doi_val).strip() if doi_val else "",
                        "raw_line": line.strip()
                    })
                except Exception:
                    references.append({
                        "index": idx,
                        "line_number": idx,
                        "text": line.strip(),
                        "doi": "",
                        "raw_line": line.strip()
                    })
    else:
        # Default to plain text
        with open(input_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                val = line.strip()
                if val:
                    references.append({
                        "index": idx,
                        "line_number": idx,
                        "text": val,
                        "doi": "",
                        "raw_line": val
                    })
    return references


def build_anomaly_record(
    finding_id: str,
    rule_id: str,
    risk: str,
    title: dict[str, str],
    summary: dict[str, str],
    safe_report_lang: str,
    evidence_source: str,
    evidence_location: str,
    quote: str | None,
    requests_en: list[str],
    requests_zh: list[str],
    alternatives: list[dict[str, str]],
    limitations: list[dict[str, str]],
    false_positives: list[dict[str, str]],
    provenance: dict[str, Any],
) -> EvidenceRecord:
    # Ensure needs_manual_review matches risk
    needs_manual_review = risk in ("high", "medium")

    evidence = [
        EvidenceLocation(
            source=evidence_source,
            location=evidence_location,
            quote=quote,
            metadata={
                "rule_id": rule_id,
                "risk_level": risk,
            }
        )
    ]

    manual_verification = ManualVerification(
        needed=needs_manual_review,
        requests=[
            {"en": req_en, "zh": req_zh}
            for req_en, req_zh in zip(requests_en, requests_zh)
        ]
    )

    risk_signal = RiskSignal(
        risk_level=risk,
        rule_id=rule_id,
        workflow_id="reference_scan",
        confidence=1.0,
    )

    report_guard = ReportLanguageGuard(
        safe_report_language=safe_report_lang,
        forbidden_verdict_phrases_blocked=True,
        requires_manual_verification_language=True,
    )

    return EvidenceRecord(
        finding_id=finding_id,
        finding_category="reference_anomaly",
        type=rule_id,
        title=title,
        summary=summary,
        risk=risk,
        risk_level=risk,
        needs_manual_review=needs_manual_review,
        evidence=evidence,
        manual_verification=manual_verification,
        false_positive_risks=false_positives,
        alternative_explanations=alternatives,
        limitations=limitations,
        provenance=provenance,
        rule_id=rule_id,
        safe_report_language=safe_report_lang,
        risk_signal=risk_signal,
        report_language_guard=report_guard,
    )


def generate_scan_summary_md(
    output_path: Path,
    input_file_name: str,
    lookup_mode: str,
    records: list[EvidenceRecord],
) -> None:
    total_anomalies = len(records)

    # Count risks
    high_cnt = sum(1 for r in records if r.risk == "high")
    med_cnt = sum(1 for r in records if r.risk == "medium")
    low_cnt = sum(1 for r in records if r.risk == "low")

    lines = [
        "# Reference Anomaly Scan Summary",
        "",
        "## Run Configuration",
        f"- **Input file**: `{input_file_name}`",
        f"- **Lookup mode**: `{lookup_mode}`",
        f"- **Total anomaly findings**: {total_anomalies} (High: {high_cnt}, Medium: {med_cnt}, Low: {low_cnt})",
        "",
        "## Safety Notice",
        "> [not_proof_of_misconduct_alert]",
        "> **Bibliographic integrity fingerprint only, not proof of research misconduct.**",
        "> Citation formatting anomalies, missing DOIs, duplicate entries, or resolved retracted status context do not determine research misconduct. These metadata anomalies are candidate signals requiring manual verification and often result from database formatting discrepancies, honest publisher updates, or citation editing utility issues.",
        "",
        "## Anomaly Ledger",
        "",
        "| Line / Index | Anomaly Type | Target Identifier | Risk Level | Safe Report Language |",
        "| --- | --- | --- | --- | --- |",
    ]

    for r in records:
        loc = r.evidence[0].location if r.evidence else "Unknown"
        rule = r.rule_id or "unknown"
        prov = r.provenance
        target = prov.get("doi") or prov.get("raw_doi") or prov.get("duplicate_item") or "N/A"
        risk = r.risk
        safe_lang = r.safe_report_language
        if isinstance(safe_lang, dict):
            safe_text = safe_lang.get("en", "")
        else:
            safe_text = str(safe_lang or "")

        lines.append(f"| `{loc}` | `{rule}` | `{target}` | `{risk}` | {safe_text} |")

    lines.extend([
        "",
        "## Limitations",
        "- The reference scan is executed in offline-first mode by default.",
        "- Malformed DOI patterns are identified via structural format syntax check only.",
        "- Status context detection (retraction, correction, EOC) is limited to cached Crossref entries or local mock fixtures.",
        "",
    ])

    # Convert placeholders to GFM
    content = "\n".join(lines).replace("[not_proof_of_misconduct_alert]", "!IMPORTANT")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def run_reference_scan(
    input_path: Path | str,
    allow_network: bool = False,
    mailto: str | None = None,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path]:
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # 1. Extract references
    references = extract_references(input_path)
    lookup_mode = "allow-network" if allow_network else "offline"

    records = []

    # Track duplicates
    seen_dois: dict[str, list[dict[str, Any]]] = {}
    seen_texts: dict[str, list[dict[str, Any]]] = {}

    for ref in references:
        text = ref["text"]

        # Gather DOI candidates
        candidates = []
        if ref["doi"]:
            candidates.append(ref["doi"])
        else:
            candidates.extend(extract_doi_candidates(text))

        # De-duplicate candidates for this line
        candidates = list(dict.fromkeys(candidates))

        normalized_dois = []
        for raw_doi in candidates:
            # Check format rules: must match 10.xxxx/yyyy pattern (4 to 9 digits for prefix)
            # and contain only valid DOI characters (no backslashes or spaces)
            is_valid = bool(re.match(r"^10\.\d{4,9}/[a-zA-Z0-9\-._;()/:~]+$", raw_doi))

            if not is_valid:
                finding_id = f"ref_anomaly_malformed_doi_{ref['index']}"
                records.append(build_anomaly_record(
                    finding_id=finding_id,
                    rule_id="malformed_doi",
                    risk="low",
                    title={
                        "en": f"Malformed DOI Pattern: {raw_doi}",
                        "zh": f"格式错误的 DOI 模式: {raw_doi}",
                    },
                    summary={
                        "en": f"Citation on line {ref['line_number']} contains a malformed DOI pattern '{raw_doi}'.",
                        "zh": f"第 {ref['line_number']} 行的引用包含格式错误的 DOI 模式 '{raw_doi}'。",
                    },
                    safe_report_lang=f"Citation contains a malformed DOI pattern '{raw_doi}'; verify the DOI suffix or URL prefix to ensure proper citation resolution.",
                    evidence_source=input_path.name,
                    evidence_location=f"Line {ref['line_number']}",
                    quote=text,
                    requests_en=[f"Verify the DOI '{raw_doi}' format against standard Registries."],
                    requests_zh=[f"对照标准注册库核实 DOI '{raw_doi}' 的格式。"],
                    alternatives=[{
                        "en": "Export utility parsing error or typographic character mismatch.",
                        "zh": "导出工具解析错误或排版字符不匹配。"
                    }],
                    limitations=[{
                        "en": "Pattern check matches string structures only and does not query DOI databases.",
                        "zh": "模式检查仅匹配字符串结构，不查询 DOI 数据库。"
                    }],
                    false_positives=[{
                        "en": "Custom private DOI publishers not standardly indexed.",
                        "zh": "未被标准索引的自定义私有 DOI 出版商。"
                    }],
                    provenance={
                        "line_number": ref["line_number"],
                        "raw_doi": raw_doi,
                    }
                ))
            else:
                try:
                    norm = normalize_doi(raw_doi)
                    normalized_dois.append(norm)
                except ValueError:
                    finding_id = f"ref_anomaly_malformed_doi_{ref['index']}"
                    records.append(build_anomaly_record(
                        finding_id=finding_id,
                        rule_id="malformed_doi",
                        risk="low",
                        title={
                            "en": f"Malformed DOI Pattern: {raw_doi}",
                            "zh": f"格式错误的 DOI 模式: {raw_doi}",
                        },
                        summary={
                            "en": f"Citation on line {ref['line_number']} contains a malformed DOI pattern '{raw_doi}'.",
                            "zh": f"第 {ref['line_number']} 行的引用包含格式错误的 DOI 模式 '{raw_doi}'。",
                        },
                        safe_report_lang=f"Citation contains a malformed DOI pattern '{raw_doi}'; verify the DOI suffix or URL prefix to ensure proper citation resolution.",
                        evidence_source=input_path.name,
                        evidence_location=f"Line {ref['line_number']}",
                        quote=text,
                        requests_en=[f"Verify the DOI '{raw_doi}' format against standard Registries."],
                        requests_zh=[f"对照标准注册库核实 DOI '{raw_doi}' 的格式。"],
                        alternatives=[{
                            "en": "Export utility parsing error or typographic character mismatch.",
                            "zh": "导出工具解析错误或排版字符不匹配。"
                        }],
                        limitations=[{
                            "en": "Pattern check matches string structures only and does not query DOI databases.",
                            "zh": "模式检查仅匹配字符串结构，不查询 DOI 数据库。"
                        }],
                        false_positives=[{
                            "en": "Custom private DOI publishers not standardly indexed.",
                            "zh": "未被标准索引的自定义私有 DOI 出版商。"
                        }],
                        provenance={
                            "line_number": ref["line_number"],
                            "raw_doi": raw_doi,
                        }
                    ))

        # Track DOI duplicates
        for normalized_doi in normalized_dois:
            if normalized_doi in seen_dois:
                seen_dois[normalized_doi].append(ref)
            else:
                seen_dois[normalized_doi] = [ref]

        # Track text duplicates (only if no DOI and non-empty text)
        if text and not candidates:
            if text in seen_texts:
                seen_texts[text].append(ref)
            else:
                seen_texts[text] = [ref]

        # Rule 2: Missing DOI Check (only if non-empty text and no DOI detected)
        if text and not candidates:
            finding_id = f"ref_anomaly_missing_doi_{ref['index']}"
            records.append(build_anomaly_record(
                finding_id=finding_id,
                rule_id="missing_doi",
                risk="low",
                title={
                    "en": "Missing DOI in Reference Citation",
                    "zh": "文献引用中缺失 DOI",
                },
                summary={
                    "en": f"Reference citation on line {ref['line_number']} is missing a DOI identifier.",
                    "zh": f"第 {ref['line_number']} 行的文献引用缺失 DOI 标识符。",
                },
                safe_report_lang="Reference citation metadata is missing a DOI identifier; verify the reference to confirm if a stable DOI identifier is available.",
                evidence_source=input_path.name,
                evidence_location=f"Line {ref['line_number']}",
                quote=text,
                requests_en=["Check the cited reference to verify metadata availability."],
                requests_zh=["检查引用的文献以核实元数据的可用性。"],
                alternatives=[{
                    "en": "The cited work is a dataset, report, web page, or older article without a DOI.",
                    "zh": "引用的文献是数据集、报告、网页或没有 DOI 的较早文章。"
                }],
                limitations=[{
                    "en": "Heuristic search cannot confirm if a DOI exists for the cited publication.",
                    "zh": "启发式搜索无法确认所引用的出版物是否存在 DOI。"
                }],
                false_positives=[{
                    "en": "Legitimate citation formats without digital identifiers.",
                    "zh": "没有数字标识符 of 合法引用格式。"
                }],
                provenance={
                    "line_number": ref["line_number"],
                    "text": text,
                }
            ))

        # Rule 3: Suspiciously Incomplete Reference Metadata (completeness signal)
        if text:
            has_year = any(1900 <= int(y) <= 2030 for y in re.findall(r"\b\d{4}\b", text))
            is_too_short = len(text) < 20

            if is_too_short or not has_year:
                finding_id = f"ref_anomaly_incomplete_ref_{ref['index']}"
                records.append(build_anomaly_record(
                    finding_id=finding_id,
                    rule_id="incomplete_reference_metadata",
                    risk="low",
                    title={
                        "en": "Incomplete Reference Metadata",
                        "zh": "不完整的文献元数据",
                    },
                    summary={
                        "en": f"Reference citation on line {ref['line_number']} appears incomplete or is missing key details (e.g. publication year).",
                        "zh": f"第 {ref['line_number']} 行的文献引用似乎不完整或缺失关键细节（例如出版年份）。",
                    },
                    safe_report_lang="Reference string is suspiciously short or missing standard bibliographic details (e.g., publication year); verify the citation metadata completeness.",
                    evidence_source=input_path.name,
                    evidence_location=f"Line {ref['line_number']}",
                    quote=text,
                    requests_en=["Verify that the bibliography item contains complete metadata."],
                    requests_zh=["核实参考文献条目是否包含完整的元数据。"],
                    alternatives=[{
                        "en": "Informal references, standards, software tools, or shorthand citations.",
                        "zh": "非正式引用、标准、软件工具或简写引用。"
                    }],
                    limitations=[{
                        "en": "Heuristics do not analyze natural language citation syntax parses.",
                        "zh": "启发式规则不分析自然语言引用语法解析。"
                    }],
                    false_positives=[{
                        "en": "Brief citation styles or short links.",
                        "zh": "简短的引用格式或短链接。"
                    }],
                    provenance={
                        "line_number": ref["line_number"],
                        "length": len(text),
                        "has_year": has_year,
                    }
                ))

        # Rule 4: Retracted / Correction / EOC Status Check (Offline Cache/Fixture Lookup)
        for normalized_doi in normalized_dois:
            try:
                work_json = fetch_crossref_work(
                    normalized_doi,
                    allow_network=allow_network,
                    mailto=mailto,
                )
                overall_status, updates, title = parse_doi_status(work_json)

                if overall_status in ("retraction", "withdrawal", "expression_of_concern", "correction"):
                    if overall_status in ("retraction", "withdrawal"):
                        status_risk = "high"
                        rule_id = "retracted_reference"
                        title_en = f"Retracted Reference Citation: {normalized_doi}"
                        title_zh = f"已被撤稿的参考文献引用: {normalized_doi}"
                        summary_en = f"Reference citation DOI '{normalized_doi}' is resolved to status 'retracted' in Crossref metadata."
                        summary_zh = f"参考文献引用 DOI '{normalized_doi}' 在 Crossref 元数据中被解析为 '撤稿' 状态。"
                    elif overall_status == "expression_of_concern":
                        status_risk = "medium"
                        rule_id = "expression_of_concern_reference"
                        title_en = f"Reference Citation with Expression of Concern: {normalized_doi}"
                        title_zh = f"含关注声明的参考文献引用: {normalized_doi}"
                        summary_en = f"Reference citation DOI '{normalized_doi}' is resolved to status 'expression of concern' in Crossref metadata."
                        summary_zh = f"参考文献引用 DOI '{normalized_doi}' 在 Crossref 元数据中被解析为 '关注声明' 状态。"
                    else:
                        status_risk = "low"
                        rule_id = "corrected_reference"
                        title_en = f"Corrected Reference Citation: {normalized_doi}"
                        title_zh = f"含勘误/修正的参考文献引用: {normalized_doi}"
                        summary_en = f"Reference citation DOI '{normalized_doi}' is resolved to status 'correction' in Crossref metadata."
                        summary_zh = f"参考文献引用 DOI '{normalized_doi}' 在 Crossref 元数据中被解析为 '修正/勘误' 状态。"

                    finding_id = f"ref_anomaly_{rule_id}_{ref['index']}"

                    status_zh = STATUS_ZH_MAP.get(overall_status, overall_status)

                    records.append(build_anomaly_record(
                        finding_id=finding_id,
                        rule_id=rule_id,
                        risk=status_risk,
                        title={
                            "en": title_en,
                            "zh": title_zh,
                        },
                        summary={
                            "en": summary_en,
                            "zh": summary_zh,
                        },
                        safe_report_lang=f"Reference citation DOI '{normalized_doi}' is resolved to status '{overall_status}' in publication records. Note: status context is not proof of misconduct.",
                        evidence_source=input_path.name,
                        evidence_location=f"Line {ref['line_number']}",
                        quote=text,
                        requests_en=[f"Verify the status '{overall_status}' notice on the journal website to understand the context."],
                        requests_zh=[f"在期刊网站上核实状态 '{overall_status}' 的具体通知以了解上下文背景。"],
                        alternatives=[{
                            "en": "The cited retraction or correction does not imply research misconduct. It can result from honest scientific error, author correction, or administrative publisher updates.",
                            "zh": "引用的撤稿或勘误通知并不意味着学术不端。它们可能源于诚实的科学错误、作者更正或出版商的行政更新。"
                        }],
                        limitations=[{
                            "en": "Status is parsed from Crossref update metadata only.",
                            "zh": "状态仅从 Crossref 更新元数据中解析。"
                        }],
                        false_positives=[{
                            "en": "Crossref update metadata may be misclassified or delayed.",
                            "zh": "Crossref 更新元数据可能分类错误或延迟。"
                        }],
                        provenance={
                            "line_number": ref["line_number"],
                            "doi": normalized_doi,
                            "raw_status": overall_status,
                            "status_relations": updates,
                        }
                    ))
            except Exception:
                pass

    # Rule 5: Duplicate Reference entries
    # For DOI duplicates:
    for doi, refs in seen_dois.items():
        if len(refs) > 1:
            for duplicate_ref in refs[1:]:
                finding_id = f"ref_anomaly_duplicate_reference_doi_{duplicate_ref['index']}"
                records.append(build_anomaly_record(
                    finding_id=finding_id,
                    rule_id="duplicate_reference",
                    risk="low",
                    title={
                        "en": f"Duplicate Reference Entry (DOI: {doi})",
                        "zh": f"重复的文献引用条目 (DOI: {doi})",
                    },
                    summary={
                        "en": f"Reference citation on line {duplicate_ref['line_number']} contains a duplicate DOI '{doi}' that was already cited on line {refs[0]['line_number']}.",
                        "zh": f"第 {duplicate_ref['line_number']} 行的文献引用包含一个重复的 DOI '{doi}'，该 DOI 已在第 {refs[0]['line_number']} 行被引用。",
                    },
                    safe_report_lang=f"Duplicate citation identifier or reference string detected in the references list (DOI/Ref: '{doi}'); verify if this is an expected duplicate citation or a citation layout discrepancy.",
                    evidence_source=input_path.name,
                    evidence_location=f"Line {duplicate_ref['line_number']}",
                    quote=duplicate_ref["text"],
                    requests_en=["Verify the bibliography list and check whether duplicate citation entries are redundant."],
                    requests_zh=["检查参考文献列表并核实重复的引用条目是否多余。"],
                    alternatives=[{
                        "en": "Intention to reference the same source under different subsections or chapters.",
                        "zh": "有意在不同章节或子部分中引用同一来源。"
                    }],
                    limitations=[{
                        "en": "Checks only for identical DOI matches in the provided references file.",
                        "zh": "仅检查所提供的参考文献文件中完全相同的 DOI 匹配。"
                    }],
                    false_positives=[{
                        "en": "Intended separate citations referencing different pages of the same source.",
                        "zh": "有意分别引用同一来源不同页面的独立引文。"
                    }],
                    provenance={
                        "line_number": duplicate_ref["line_number"],
                        "original_line_number": refs[0]["line_number"],
                        "duplicate_item": doi,
                    }
                ))

    # For text duplicates (without DOIs):
    for txt, refs in seen_texts.items():
        if len(refs) > 1:
            for duplicate_ref in refs[1:]:
                truncated_txt = txt[:30] + "..." if len(txt) > 30 else txt
                finding_id = f"ref_anomaly_duplicate_reference_text_{duplicate_ref['index']}"
                records.append(build_anomaly_record(
                    finding_id=finding_id,
                    rule_id="duplicate_reference",
                    risk="low",
                    title={
                        "en": f"Duplicate Reference Entry (Text: {truncated_txt})",
                        "zh": f"重复的文献引用条目 (文本: {truncated_txt})",
                    },
                    summary={
                        "en": f"Reference citation on line {duplicate_ref['line_number']} is identical to reference on line {refs[0]['line_number']}.",
                        "zh": f"第 {duplicate_ref['line_number']} 行的文献引用与第 {refs[0]['line_number']} 行的引用完全相同。",
                    },
                    safe_report_lang=f"Duplicate citation identifier or reference string detected in the references list (DOI/Ref: '{truncated_txt}'); verify if this is an expected duplicate citation or a citation layout discrepancy.",
                    evidence_source=input_path.name,
                    evidence_location=f"Line {duplicate_ref['line_number']}",
                    quote=duplicate_ref["text"],
                    requests_en=["Verify the bibliography list and check whether duplicate citation entries are redundant."],
                    requests_zh=["检查参考文献列表并核实重复的引用条目是否多余。"],
                    alternatives=[{
                        "en": "Intention to reference the same source under different subsections or chapters.",
                        "zh": "有意在不同章节或子部分中引用同一来源。"
                    }],
                    limitations=[{
                        "en": "Checks only for identical text matches in the provided references file.",
                        "zh": "仅检查所提供的参考文献文件中完全相同的文本匹配。"
                    }],
                    false_positives=[{
                        "en": "Intended separate citations referencing different parts of the same manual.",
                        "zh": "有意分别引用同一手册不同部分的独立引文。"
                    }],
                    provenance={
                        "line_number": duplicate_ref["line_number"],
                        "original_line_number": refs[0]["line_number"],
                        "duplicate_item": txt,
                    }
                ))

    # 3. Write outputs
    if output_dir is None:
        resolved_out_dir = DEFAULT_OUTPUT_DIR
    else:
        resolved_out_dir = Path(output_dir)

    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = resolved_out_dir / "reference_anomalies.jsonl"
    summary_path = resolved_out_dir / "reference_anomaly_summary.md"

    # Write JSONL
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json(by_alias=True) + "\n")

    # Write summary markdown
    generate_scan_summary_md(
        summary_path,
        input_file_name=input_path.name,
        lookup_mode=lookup_mode,
        records=records,
    )

    return jsonl_path.resolve(), summary_path.resolve()
