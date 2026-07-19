from __future__ import annotations

from pathlib import Path
from typing import Any

from integrity_agent.core.evidence.scope import split_public_records
from integrity_agent.core.safety import find_runtime_safety_issues
from integrity_agent.workflows.run_rules import iter_rule_findings


DEFAULT_REPORT = Path("outputs") / "reader_review_report.md"


def _display_path(path_like: object, *, root: Path | None = None) -> str:
    """Render user-facing paths as repo-relative POSIX paths when possible."""
    if path_like is None:
        return ""
    raw = str(path_like)
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return raw.replace("\\", "/")
    try:
        base = Path.cwd() if root is None else root
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        # Do not persist machine-specific absolute paths in reader-facing reports.
        return path.name


def _bullet(items: list[str]) -> str:
    if not items:
        return "- None recorded.\n"
    return "".join(f"- {item}\n" for item in items)


def _resolve_str(val: Any) -> str:
    if not val:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("en") or val.get("zh") or next(iter(val.values()), "")
    return str(val)


def _record_value(record: dict[str, Any], key: str) -> Any:
    for container in (
        record,
        record.get("provenance"),
        record.get("metadata"),
    ):
        if isinstance(container, dict) and container.get(key) not in (None, ""):
            return container[key]
    return None


def _counter_evidence_text(value: Any) -> str:
    if not value:
        return "None recorded."
    if not isinstance(value, list):
        value = [value]
    rendered: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            rendered.append(_resolve_str(item))
            continue
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
        rendered.append(", ".join(parts) or str(item))
    return "; ".join(rendered)


def _structured_context_lines(record: dict[str, Any]) -> list[str]:
    evidence_tier = _record_value(record, "evidence_tier")
    source_version = _record_value(record, "source_version")
    resolution_status = _record_value(record, "resolution_status")
    counter_evidence = _record_value(record, "counter_evidence")
    do_not_overclaim = _record_value(record, "do_not_overclaim")
    if not any(
        value
        for value in (
            evidence_tier,
            source_version,
            resolution_status,
            counter_evidence,
            do_not_overclaim,
        )
    ):
        return []

    evidence = record.get("evidence") or record.get("evidence_items") or []
    source_fact = "None recorded."
    if evidence and isinstance(evidence[0], dict):
        source = _display_path(evidence[0].get("source") or "")
        location = evidence[0].get("location") or ""
        source_fact = f"{source} at {location}".strip()
    manual = record.get("manual_verification") or []
    if isinstance(manual, dict):
        manual = manual.get("requests") or []
    verification = _resolve_str(manual[0]) if manual else "None recorded."
    mechanism = _record_value(record, "mechanism_interpretation") or (
        "No mechanism, intent, or responsibility is inferred from this signal."
    )
    detector_result = _resolve_str(
        record.get("safe_report_language") or record.get("summary") or ""
    )
    return [
        f"### `{record.get('finding_id') or record.get('rule_id') or 'finding'}`",
        f"- Source fact: {source_fact}",
        f"- Detector/recomputation result: {detector_result or 'None recorded.'}",
        f"- Mechanism interpretation: {_resolve_str(mechanism)}",
        f"- Transferability/verification request: {verification}",
        f"- Evidence tier: {evidence_tier or 'Not assigned.'}",
        f"- Source version: {source_version or 'Not recorded.'}",
        f"- Resolution status: {resolution_status or 'open'}",
        f"- Counter-evidence: {_counter_evidence_text(counter_evidence)}",
        f"- Do-not-overclaim: {_resolve_str(do_not_overclaim) or 'Treat as a candidate signal requiring human review.'}",
        "",
    ]


def _pv_source_context(record: dict[str, Any]) -> tuple[str, str]:
    source = record.get("source_file") or record.get("relative_path")
    table_id = record.get("table_id")
    evidence = record.get("evidence") or record.get("evidence_items") or []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source = source or item.get("source") or item.get("relative_path")
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            table_id = table_id or metadata.get("table_id") or metadata.get("table")
        table_id = table_id or item.get("table")
    provenance = record.get("provenance") or record.get("metadata") or {}
    if isinstance(provenance, dict):
        source = source or provenance.get("source_file") or provenance.get("source")
        table_id = table_id or provenance.get("table_id") or provenance.get("table")
    return _display_path(source or "unknown_file"), str(table_id or "not recorded")


def write_reader_review_report(
    findings_path: Path | str,
    output_path: Path | str = DEFAULT_REPORT,
    *,
    artifact_root: Path | str | None = None,
) -> Path:
    findings_path = Path(findings_path)
    findings_path = findings_path.expanduser()
    if not findings_path.is_absolute():
        findings_path = Path.cwd() / findings_path
    findings = list(iter_rule_findings(findings_path))
    safety_issues = find_runtime_safety_issues(findings)
    if safety_issues:
        raise ValueError(
            "unsafe findings content: "
            + "; ".join(sorted(set(safety_issues)))
        )

    output_path = Path(output_path)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    has_explicit_artifact_root = artifact_root is not None
    artifact_root = Path.cwd() / "outputs" if artifact_root is None else Path(artifact_root)
    if not artifact_root.is_absolute():
        artifact_root = Path.cwd() / artifact_root
    findings_display_root = artifact_root if has_explicit_artifact_root else Path.cwd()

    # Dedup findings loaded from findings_path
    processed_finding_ids = set()
    deduped_findings = []
    for finding in findings:
        fid = finding.get("finding_id") or finding.get("item_id")
        rule_id = finding.get("rule_id", "unknown_rule")
        src_file = finding.get("source_file") or finding.get("relative_path", "unknown_file")
        safe_lang = finding.get("safe_report_language", "")
        composite = (rule_id, src_file, str(safe_lang))

        # Check if already processed
        if (fid and fid in processed_finding_ids) or composite in processed_finding_ids:
            continue

        if fid:
            processed_finding_ids.add(fid)
        processed_finding_ids.add(composite)
        deduped_findings.append(finding)

    findings, engineering_findings = split_public_records(deduped_findings)

    risk_lines = []
    for finding in findings:
        safe_lang = finding.get("safe_report_language", "")
        if isinstance(safe_lang, dict):
            safe_lang = safe_lang.get("en") or safe_lang.get("zh") or next(iter(safe_lang.values()), "")
        risk_lines.append(f"`{finding['rule_id']}` ({finding['risk_level']}): {safe_lang}")

    engineering_lines = []
    for question in engineering_findings:
        safe_lang = _resolve_str(
            question.get("safe_report_language") or question.get("summary") or ""
        )
        rule_id = question.get("rule_id") or question.get("type") or "engineering_question"
        engineering_lines.append(f"`{rule_id}`: {safe_lang}")

    evidence_lines = []
    alternatives: list[str] = []
    missing: list[str] = []
    questions: list[str] = []
    limitations: list[str] = []
    structured_context: list[str] = []
    for finding in findings:
        structured_context.extend(_structured_context_lines(finding))
        ev_items = finding.get("evidence_items") or finding.get("evidence") or []
        for item in ev_items:
            evidence_lines.append(
                f"`{finding['rule_id']}`: {_display_path(item.get('source'))} at {item.get('location')}"
            )
        alternatives.extend([_resolve_str(x) for x in finding.get("alternative_explanations", [])])

        mv = finding.get("manual_verification")
        if isinstance(mv, dict):
            mv_reqs = mv.get("requests", [])
        elif isinstance(mv, list):
            mv_reqs = mv
        else:
            mv_reqs = []
        for req in mv_reqs:
            missing.append(_resolve_str(req))
        missing.extend([_resolve_str(x) for x in finding.get("missing_verification_materials", [])])

        q_list = finding.get("suggested_verification_questions") or finding.get("verification_questions") or []
        for q in q_list:
            if isinstance(q, dict):
                text_val = q.get("text") or q.get("en") or q.get("zh")
                if text_val:
                    questions.append(_resolve_str(text_val))
            else:
                questions.append(_resolve_str(q))

        lims = finding.get("limitations", [])
        if isinstance(lims, list):
            limitations.extend([_resolve_str(x) for x in lims])
        else:
            limitations.append(_resolve_str(lims))

    # Load exact duplicate image findings if present
    import json
    image_findings_path = artifact_root / "image_intake/image_findings.jsonl"

    if image_findings_path.exists():
        try:
            with open(image_findings_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        img_f = json.loads(line)
                        rule_id = img_f["rule_id"]
                        fid = img_f.get("finding_id") or img_f.get("item_id")
                        src_file = img_f.get("source_file") or img_f.get("relative_path")
                        safe_lang = img_f["safe_report_language"]
                        composite = (rule_id, src_file, safe_lang)
                        if (fid and fid in processed_finding_ids) or composite in processed_finding_ids:
                            continue

                        risk_level = img_f["risk_level"]
                        risk_lines.append(f"`{rule_id}` ({risk_level}): {safe_lang}")

                        for ev in img_f.get("evidence_items", []):
                            path_str = _display_path(ev.get("relative_path", ""))
                            evidence_lines.append(f"`{rule_id}`: {path_str} at exact duplicate SHA256")

                        alternatives.extend(img_f.get("alternative_explanations", []))
                        missing.extend(img_f.get("manual_verification", []))
                        questions.append("Please clarify whether duplicate panels represent independent experimental runs or identical control samples.")
                        questions.append("Please provide original unprocessed image files, acquisition metadata, and author explanation.")
                        limitations.append("exact duplicate check is limited to file-level SHA256 hashes.")
        except Exception:
            pass

    # Load visual similarity image candidates if present
    similarity_candidates_path = artifact_root / "image_intake/image_similarity_candidates.jsonl"

    if similarity_candidates_path.exists():
        try:
            with open(similarity_candidates_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        cand = json.loads(line)
                        rule_id = cand["rule_id"]
                        fid = cand.get("finding_id") or cand.get("item_id")
                        src_file = cand.get("source_file") or cand.get("relative_path_a")
                        safe_lang = cand["safe_report_language"]
                        composite = (rule_id, src_file, safe_lang)
                        if (fid and fid in processed_finding_ids) or composite in processed_finding_ids:
                            continue

                        risk_level = cand["risk_level"]

                        risk_str = f"`{rule_id}` ({risk_level}): {safe_lang}"
                        if risk_str not in risk_lines:
                            risk_lines.append(risk_str)

                        path_a = _display_path(cand.get("relative_path_a", ""))
                        path_b = _display_path(cand.get("relative_path_b", ""))
                        dist = cand.get("hamming_distance", 0)
                        evidence_lines.append(
                            f"`{rule_id}`: {path_a} at visually similar to {path_b} (Hamming distance {dist})"
                        )

                        alternatives.extend(cand.get("alternative_explanations", []))
                        missing.extend(cand.get("manual_verification", []))
                        questions.append("Please clarify whether visually similar panels represent independent experimental runs or identical control samples.")
                        questions.append("Please provide original unprocessed image files, acquisition metadata, and author explanation.")
                        limitations.extend(cand.get("limitations", []))
        except Exception:
            pass

    # Load table numeric findings if present
    table_findings_path = artifact_root / "table_intake/table_numeric_findings.jsonl"

    if table_findings_path.exists():
        try:
            with open(table_findings_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        tbl_f = json.loads(line)
                        rule_id = tbl_f["rule_id"]
                        fid = tbl_f.get("finding_id") or tbl_f.get("item_id")
                        src_file = tbl_f.get("source_file") or tbl_f.get("relative_path")
                        safe_lang = tbl_f["safe_report_language"]
                        composite = (rule_id, src_file, safe_lang)
                        if (fid and fid in processed_finding_ids) or composite in processed_finding_ids:
                            continue

                        risk_level = tbl_f["risk_level"]

                        risk_str = f"`{rule_id}` ({risk_level}): {safe_lang}"
                        if risk_str not in risk_lines:
                            risk_lines.append(risk_str)

                        src_file = _display_path(tbl_f.get("source_file", ""))
                        cols_list = tbl_f.get("column_names", [])
                        row_rng = tbl_f.get("row_range", "")
                        evidence_lines.append(
                            f"`{rule_id}`: {src_file} at columns {', '.join(cols_list)} ({row_rng})"
                        )

                        alternatives.extend(tbl_f.get("alternative_explanations", []))
                        missing.extend(tbl_f.get("manual_verification", []))
                        questions.append("Please clarify whether tabular columns represent independent measurements or derived formula values.")
                        questions.append("Please provide the raw spreadsheets and formula scripts.")
                        limitations.append("table numeric checks are limited to the provided source data and rules.")
        except Exception:
            pass

    metadata_path = artifact_root / "paper_case/metadata.json"

    metadata_summary = []
    if metadata_path.exists():
        try:
            import json
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            doi_val = meta.get("normalized_doi", "unknown")
            status_val = meta.get("status", "unknown")
            source_val = meta.get("source_strength", "unknown")
            title_val = meta.get("title", "Unknown Title")
            pub_val = meta.get("publisher", "Unknown Publisher")

            if status_val == "no_known_update":
                status_desc = "no known update found in available metadata"
            else:
                status_desc = status_val

            metadata_summary = [
                f"- Target DOI: `{doi_val}` (status: `{status_desc}`, source: `{source_val}`)",
                f"- Title: {title_val}",
                f"- Publisher: {pub_val}",
            ]
        except Exception:
            pass

    metadata_section = [
        "# Reader Review Report",
        "",
        "## Metadata and source status",
        f"- Findings source: `{_display_path(findings_path, root=findings_display_root)}`",
        f"- Finding count: {len(findings)}",
        "- Runtime mode: local toy/stub rule execution.",
    ]
    if engineering_findings:
        metadata_section.append(f"- Engineering question count: {len(engineering_findings)}")
    if metadata_summary:
        metadata_section.extend(metadata_summary)
    metadata_section.append("")

    # Load PV findings if present
    pv_findings_path = artifact_root / "pv_domain/pv_findings.jsonl"

    pv_section_lines = []
    pv_findings = []
    if pv_findings_path.exists():
        try:
            with open(pv_findings_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        pv_findings.append(json.loads(line))
        except Exception:
            pass

    if not pv_findings:
        pv_rules = {
            "pv_pce_consistency",
            "pv_eqe_jv_jsc_consistency",
            "pv_voc_loss_consistency",
            "pv_reporting_completeness",
            "pv_stability_reporting_completeness",
            "pv_tandem_current_matching",
            "pv_materials_characterization_metadata",
        }
        pv_findings = [f for f in findings if f.get("rule_id") in pv_rules]

    if pv_findings:
        pce_s = []
        eqe_s = []
        voc_s = []
        rep_s = []
        stab_s = []
        tan_s = []
        mat_s = []
        questions_s = []

        for finding in pv_findings:
            rule_id = finding["rule_id"]
            risk_level = finding["risk_level"]
            safe_lang = finding["safe_report_language"]
            source_file, table_id = _pv_source_context(finding)
            row_idx = finding.get("row_index")
            row_str = f" (Row {row_idx})" if row_idx else ""

            finding_str = (
                f"`{finding['finding_id']}` ({risk_level}): {safe_lang} "
                f"[File: `{source_file}` / Table: `{table_id}`{row_str}]"
            )

            if rule_id == "pv_pce_consistency":
                pce_s.append(finding_str)
            elif rule_id == "pv_eqe_jv_jsc_consistency":
                eqe_s.append(finding_str)
            elif rule_id == "pv_voc_loss_consistency":
                voc_s.append(finding_str)
            elif rule_id == "pv_reporting_completeness":
                rep_s.append(finding_str)
            elif rule_id == "pv_stability_reporting_completeness":
                stab_s.append(finding_str)
            elif rule_id == "pv_tandem_current_matching":
                tan_s.append(finding_str)
            elif rule_id == "pv_materials_characterization_metadata":
                mat_s.append(finding_str)

            manual = finding.get("manual_verification", [])
            if isinstance(manual, dict):
                manual = manual.get("requests", [])
            questions_s.extend(manual)

        pv_section_lines.extend([
            "## Photovoltaics / materials domain evidence signals",
            "### PV metric consistency signals",
            _bullet(pce_s).rstrip(),
            "",
            "### EQE/J–V current-density signals",
            _bullet(eqe_s).rstrip(),
            "",
            "### Voc-loss / bandgap signals",
            _bullet(voc_s).rstrip(),
            "",
            "### Solar-cell reporting completeness gaps",
            _bullet(rep_s).rstrip(),
            "",
            "### Stability reporting gaps",
            _bullet(stab_s).rstrip(),
            "",
            "### Tandem PV consistency signals",
            _bullet(tan_s).rstrip(),
            "",
            "### Materials characterization metadata gaps",
            _bullet(mat_s).rstrip(),
            "",
            "### PV/materials verification questions",
            _bullet(sorted(list(set(questions_s)))).rstrip(),
            ""
        ])

    # Load raw PV findings if present
    raw_pv_findings_path = artifact_root / "raw_pv/raw_pv_findings.jsonl"

    raw_pv_section_lines = []
    raw_pv_findings = []
    if raw_pv_findings_path.exists():
        try:
            with open(raw_pv_findings_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        raw_pv_findings.append(json.loads(line))
        except Exception:
            pass

    if not raw_pv_findings:
        raw_pv_rules = {
            "pv_jv_metric_recalculation",
            "pv_jv_hysteresis_candidate",
            "pv_eqe_spectrum_integration",
            "pv_excel_formula_audit",
            "pv_source_reconciliation",
        }
        raw_pv_findings = [f for f in findings if f.get("rule_id") in raw_pv_rules]

    if raw_pv_findings:
            jv_recalc_s = []
            jv_hyst_s = []
            eqe_int_s = []
            rec_s = []
            excel_s = []
            raw_questions_s = []

            for f in raw_pv_findings:
                rule_id = f["rule_id"]
                risk_level = f["risk_level"]
                safe_lang = f["safe_report_language"]
                source_file = _display_path(f["source_file"])
                dev_id = f.get("device_id")
                dev_str = f" / Device: `{dev_id}`" if dev_id else ""

                finding_str = f"`{f['finding_id']}` ({risk_level}): {safe_lang} [File: `{source_file}`{dev_str}]"

                if rule_id == "pv_jv_metric_recalculation":
                    jv_recalc_s.append(finding_str)
                elif rule_id == "pv_jv_hysteresis_candidate":
                    jv_hyst_s.append(finding_str)
                elif rule_id == "pv_eqe_spectrum_integration":
                    eqe_int_s.append(finding_str)
                elif rule_id == "pv_source_reconciliation":
                    rec_s.append(finding_str)
                elif rule_id == "pv_excel_formula_audit":
                    excel_s.append(finding_str)

                raw_questions_s.extend(f.get("manual_verification", []))

            raw_pv_section_lines.extend([
                "## Raw photovoltaic measurement recalculation signals",
                "### J–V metric recalculation signals",
                _bullet(jv_recalc_s).rstrip(),
                "",
                "### J–V hysteresis candidate signals",
                _bullet(jv_hyst_s).rstrip(),
                "",
                "### EQE spectrum integration signals",
                _bullet(eqe_int_s).rstrip(),
                "",
                "### Raw/reported metric reconciliation signals",
                _bullet(rec_s).rstrip(),
                "",
                "### Spreadsheet formula audit signals",
                _bullet(excel_s).rstrip(),
                "",
                "### Raw PV verification questions",
                _bullet(sorted(list(set(raw_questions_s)))).rstrip(),
                ""
            ])

    engineering_section = []
    if engineering_lines:
        engineering_section = [
            "## Engineering plausibility questions (outside integrity MRPI)",
            _bullet(engineering_lines).rstrip(),
            "",
        ]

    structured_context_section: list[str] = []
    if structured_context:
        structured_context_section = [
            "## Structured review context",
            *structured_context,
        ]

    body_list = metadata_section + [
        "## Detected risk signals",
        _bullet(risk_lines).rstrip(),
        "",
    ] + engineering_section + structured_context_section + [
        "## Evidence locations",
        _bullet(evidence_lines).rstrip(),
        "",
        "## Alternative benign explanations",
        _bullet(sorted(set(alternatives))).rstrip(),
        "",
        "## Missing verification materials",
        _bullet(sorted(set(missing))).rstrip(),
        "",
        "## Suggested verification questions",
        _bullet(sorted(set(questions))).rstrip(),
        "",
        "## Limitations",
        _bullet(sorted(set(limitations))).rstrip(),
        "",
    ]
    if pv_section_lines:
        body_list.extend(pv_section_lines)
    if raw_pv_section_lines:
        body_list.extend(raw_pv_section_lines)

    body_list.extend([
        "## Do-not-overclaim notice",
        (
            "- This report surfaces candidate risk signals for human review. "
            "It does not determine misconduct, intent, or responsibility."
        ),
        (
            "- The Manual Review Priority Index (MRPI) is an estimated density index of candidate anomalies to help prioritize manual verification. "
            "It is NOT a misconduct probability. High priority signals must always be evaluated alongside alternative benign explanations and potential limitations of the detectors."
        ),
        "",
    ])

    body = "\n".join(body_list)
    output_path.write_text(body, encoding="utf-8")
    return output_path.resolve()
