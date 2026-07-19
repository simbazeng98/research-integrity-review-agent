from __future__ import annotations

import csv
import json
from pathlib import Path

from integrity_agent.core.intake.batch_schema import BatchIntakeResult, LiteratureItem
from integrity_agent.core.intake.adapters.doi_list import parse_doi_list
from integrity_agent.core.intake.adapters.csl_json import parse_csl_json
from integrity_agent.core.intake.adapters.bibtex_basic import parse_bibtex
from integrity_agent.core.intake.adapters.ris_basic import parse_ris
from integrity_agent.core.metadata.crossref_client import (
    fetch_crossref_work,
    CrossrefClientError,
    CrossrefNotFoundError,
    CrossrefRateLimitError,
)
from integrity_agent.core.metadata.crossref_updates import parse_crossref_updates
from integrity_agent.core.output_safety import sanitize_csv_cell

DEFAULT_OUTPUT_DIR = Path("outputs") / "batch_intake"


def _write_csv_table(path: Path, items: list[LiteratureItem]) -> None:
    headers = [
        "item_id",
        "doi",
        "normalized_doi",
        "title",
        "year",
        "journal",
        "metadata_status",
        "crossref_update_status",
        "warnings",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in items:
            writer.writerow(
                [
                    sanitize_csv_cell(value)
                    for value in [
                        item.item_id,
                        item.doi or "",
                        item.normalized_doi or "",
                        item.title or "",
                        item.year or "",
                        item.journal or "",
                        item.metadata_status,
                        item.crossref_update_status,
                        "; ".join(item.warnings),
                    ]
                ]
            )


def _write_jsonl(path: Path, items: list[LiteratureItem]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def _generate_summary_md(path: Path, result: BatchIntakeResult) -> None:
    items = result.items

    retractions = [item for item in items if item.crossref_update_status == "retraction"]
    eocs = [item for item in items if item.crossref_update_status == "expression_of_concern"]
    corrections = [item for item in items if item.crossref_update_status == "correction"]

    manual_items = []
    for item in items:
        is_manual = False
        if not item.normalized_doi:
            is_manual = True
        elif item.metadata_status == "rate_limited":
            is_manual = True
        elif item.crossref_update_status in ["retraction", "correction", "expression_of_concern"]:
            is_manual = True

        if is_manual:
            manual_items.append(item)

    lines = [
        "# Batch Intake Summary Report",
        "",
        "## Batch input source",
        f"- Source file: `{result.source_file}`",
        f"- Source format: `{result.source_format}`",
        "",
        "## Number of items parsed",
        f"- Total parsed items: {result.total_items}",
        "",
        "## Number of valid DOIs",
        f"- Valid DOIs: {result.valid_dois}",
        "",
        "## Number of duplicate DOIs",
        f"- Duplicate DOIs: {result.duplicate_dois}",
        "",
        "## Metadata lookup mode: offline / allow-network",
        f"- Mode: `{result.lookup_mode}`",
        "",
        "## Retraction metadata summary",
        f"- Retractions detected: {len(retractions)}",
    ]
    if retractions:
        for r in retractions:
            lines.append(f"  - DOI: `{r.normalized_doi}` | Title: *{r.title or 'Unknown'}*")
    else:
        lines.append("  - No retraction updates detected.")

    lines.extend([
        "",
        "## Correction / expression of concern summary",
        f"- Corrections detected: {len(corrections)}",
        f"- Expressions of concern detected: {len(eocs)}",
    ])
    if corrections or eocs:
        for c in corrections:
            lines.append(f"  - [Correction] DOI: `{c.normalized_doi}` | Title: *{c.title or 'Unknown'}*")
        for e in eocs:
            lines.append(f"  - [Expression of Concern] DOI: `{e.normalized_doi}` | Title: *{e.title or 'Unknown'}*")
    else:
        lines.append("  - No corrections or expressions of concern detected.")

    lines.extend([
        "",
        "## Items requiring manual verification",
        f"- Total requiring manual review: {len(manual_items)}",
    ])
    if manual_items:
        for m in manual_items:
            reasons = []
            if not m.normalized_doi:
                reasons.append("Invalid/Missing DOI")
            if m.metadata_status == "rate_limited":
                reasons.append("Metadata rate limited")
            if m.crossref_update_status in ["retraction", "correction", "expression_of_concern"]:
                reasons.append(f"Has update status '{m.crossref_update_status}'")
            reason_str = ", ".join(reasons)
            lines.append(f"  - Item `{m.item_id}` | DOI: `{m.doi}` | Reason: {reason_str}")
    else:
        lines.append("  - No items requiring manual review.")

    lines.extend([
        "",
        "## Limitations",
        "- The batch parser uses lightweight adapters (regular expressions for BibTeX, standard library for CSL JSON and CSV/TXT).",
        "- Metadata latency or indexing lags on Crossref may result in updates not immediately appearing.",
        "- Offline mode uses static mock data or leaves metadata unchecked.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces candidate risk signals for human review. It does not determine misconduct, intent, or responsibility.",
        "- A status of `no_known_update` does not prove the paper is reliable.",
        "- A status of `metadata_unavailable` does not imply that the paper is suspicious.",
        "- A correction notice does not imply misconduct.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def run_batch_intake(
    input_path: Path | str,
    allow_network: bool = False,
    mailto: str | None = None,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path, Path]:
    """Execute the batch intake workflow for a given input file."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ext = input_path.suffix.lower()
    if ext in [".txt", ".csv"]:
        items = parse_doi_list(input_path)
        source_format = "doi_list"
    elif ext == ".json":
        items = parse_csl_json(input_path)
        source_format = "csl_json"
    elif ext == ".bib":
        items = parse_bibtex(input_path)
        source_format = "bibtex"
    elif ext == ".ris":
        items = parse_ris(input_path)
        source_format = "ris"
    else:
        raise ValueError(f"Unsupported file format extension: {ext}")

    total_items = len(items)
    valid_dois = 0
    duplicate_dois = 0
    lookup_mode = "allow-network" if allow_network else "offline"

    seen_dois: dict[str, LiteratureItem] = {}

    for item in items:
        if not item.normalized_doi:
            item.metadata_status = "failed"
            item.crossref_update_status = "metadata_unavailable"
            continue

        doi_lower = item.normalized_doi.lower()
        if doi_lower in seen_dois:
            duplicate_dois += 1
            item.warnings.append("Duplicate DOI in batch; using cached lookup.")
            
            # Copy result from first lookup
            first_item = seen_dois[doi_lower]
            item.metadata_status = first_item.metadata_status
            item.crossref_update_status = first_item.crossref_update_status
            item.title = first_item.title or item.title
            item.year = first_item.year or item.year
            item.journal = first_item.journal or item.journal
            
            for w in first_item.warnings:
                if w not in item.warnings and "Duplicate" not in w:
                    item.warnings.append(w)
        else:
            seen_dois[doi_lower] = item
            valid_dois += 1

            try:
                work_json = fetch_crossref_work(
                    item.normalized_doi,
                    allow_network=allow_network,
                    mailto=mailto
                )
                parsed = parse_crossref_updates(work_json)
                item.metadata_status = "success"
                item.crossref_update_status = parsed.status

                # Enrich metadata if available in payload
                message = work_json.get("message", {})
                titles = message.get("title", [])
                if titles and not item.title:
                    item.title = str(titles[0])

                pub = message.get("publisher")
                if pub and not item.journal:
                    item.journal = str(pub)

                issued = message.get("issued")
                if issued and not item.year:
                    date_parts = issued.get("date-parts")
                    if date_parts and date_parts[0]:
                        item.year = str(date_parts[0][0])

            except CrossrefNotFoundError as e:
                item.metadata_status = "failed"
                item.crossref_update_status = "metadata_unavailable"
                item.warnings.append(f"DOI not found on Crossref: {e}")
            except CrossrefRateLimitError as e:
                item.metadata_status = "rate_limited"
                item.crossref_update_status = "metadata_unavailable"
                item.warnings.append(f"Crossref rate limited: {e}")
            except CrossrefClientError as e:
                status_name = "offline" if not allow_network else "failed"
                item.metadata_status = status_name
                item.crossref_update_status = "metadata_unavailable"
                msg = "Metadata network lookup was not performed." if not allow_network else f"Metadata lookup failed: {e}"
                item.warnings.append(msg)

    # 4. Write outputs
    if output_dir is None:
        resolved_out_dir = DEFAULT_OUTPUT_DIR
    else:
        resolved_out_dir = Path(output_dir)

    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    result = BatchIntakeResult(
        source_file=input_path.name,
        source_format=source_format,
        total_items=total_items,
        valid_dois=valid_dois,
        duplicate_dois=duplicate_dois,
        lookup_mode=lookup_mode,
        items=items,
    )

    jsonl_path = resolved_out_dir / "batch_items.jsonl"
    csv_path = resolved_out_dir / "batch_intake_table.csv"
    summary_path = resolved_out_dir / "batch_intake_summary.md"

    _write_jsonl(jsonl_path, items)
    _write_csv_table(csv_path, items)
    _generate_summary_md(summary_path, result)

    return jsonl_path.resolve(), csv_path.resolve(), summary_path.resolve()
