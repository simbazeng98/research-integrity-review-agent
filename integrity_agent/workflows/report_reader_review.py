from __future__ import annotations

from pathlib import Path

from integrity_agent.workflows.run_rules import iter_rule_findings


DEFAULT_REPORT = Path("outputs") / "reader_review_report.md"


def _display_path(path_like: object) -> str:
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
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return raw.replace("\\", "/")


def _bullet(items: list[str]) -> str:
    if not items:
        return "- None recorded.\n"
    return "".join(f"- {item}\n" for item in items)


def write_reader_review_report(
    findings_path: Path, output_path: Path = DEFAULT_REPORT
) -> Path:
    findings_path = findings_path.expanduser()
    if not findings_path.is_absolute():
        findings_path = Path.cwd() / findings_path
    findings = list(iter_rule_findings(findings_path))

    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Dedup findings loaded from findings_path
    processed_finding_ids = set()
    deduped_findings = []
    for finding in findings:
        fid = finding.get("finding_id") or finding.get("item_id")
        rule_id = finding.get("rule_id", "unknown_rule")
        src_file = finding.get("source_file") or finding.get("relative_path", "unknown_file")
        safe_lang = finding.get("safe_report_language", "")
        composite = (rule_id, src_file, safe_lang)
        
        # Check if already processed
        if (fid and fid in processed_finding_ids) or composite in processed_finding_ids:
            continue
        
        if fid:
            processed_finding_ids.add(fid)
        processed_finding_ids.add(composite)
        deduped_findings.append(finding)
    
    findings = deduped_findings

    risk_lines = [
        f"`{finding['rule_id']}` ({finding['risk_level']}): {finding['safe_report_language']}"
        for finding in findings
    ]
    evidence_lines = []
    alternatives: list[str] = []
    missing: list[str] = []
    questions: list[str] = []
    limitations: list[str] = []
    for finding in findings:
        for item in finding.get("evidence_items", []):
            evidence_lines.append(
                f"`{finding['rule_id']}`: {_display_path(item.get('source'))} at {item.get('location')}"
            )
        alternatives.extend(finding.get("alternative_explanations", []))
        missing.extend(finding.get("missing_verification_materials", []))
        questions.extend(finding.get("suggested_verification_questions", []))
        limitations.extend(finding.get("limitations", []))

    # Load exact duplicate image findings if present
    import json
    image_findings_path = Path("outputs/image_intake/image_findings.jsonl")
    if not image_findings_path.is_absolute():
        image_findings_path = Path.cwd() / image_findings_path

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
    similarity_candidates_path = Path("outputs/image_intake/image_similarity_candidates.jsonl")
    if not similarity_candidates_path.is_absolute():
        similarity_candidates_path = Path.cwd() / similarity_candidates_path

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
    table_findings_path = Path("outputs/table_intake/table_numeric_findings.jsonl")
    if not table_findings_path.is_absolute():
        table_findings_path = Path.cwd() / table_findings_path

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

    metadata_path = Path("outputs/paper_case/metadata.json")
    if not metadata_path.is_absolute():
        metadata_path = Path.cwd() / metadata_path

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
        f"- Findings source: `{_display_path(findings_path)}`",
        f"- Finding count: {len(findings)}",
        "- Runtime mode: local toy/stub rule execution.",
    ]
    if metadata_summary:
        metadata_section.extend(metadata_summary)
    metadata_section.append("")

    # Load PV findings if present
    pv_findings_path = Path("outputs/pv_domain/pv_findings.jsonl")
    if not pv_findings_path.is_absolute():
        pv_findings_path = Path.cwd() / pv_findings_path

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

            for f in pv_findings:
                rule_id = f["rule_id"]
                risk_level = f["risk_level"]
                safe_lang = f["safe_report_language"]
                source_file = _display_path(f["source_file"])
                table_id = f["table_id"]
                row_idx = f.get("row_index")
                row_str = f" (Row {row_idx})" if row_idx else ""
                
                finding_str = f"`{f['finding_id']}` ({risk_level}): {safe_lang} [File: `{source_file}` / Table: `{table_id}`{row_str}]"
                
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

                questions_s.extend(f.get("manual_verification", []))

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
    raw_pv_findings_path = Path("outputs/raw_pv/raw_pv_findings.jsonl")
    if not raw_pv_findings_path.is_absolute():
        raw_pv_findings_path = Path.cwd() / raw_pv_findings_path

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

    body_list = metadata_section + [
        "## Detected risk signals",
        _bullet(risk_lines).rstrip(),
        "",
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
        "",
    ])

    body = "\n".join(body_list)
    output_path.write_text(body, encoding="utf-8")
    return output_path.resolve()

