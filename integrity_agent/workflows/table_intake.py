from __future__ import annotations

import csv
import json
from pathlib import Path

from integrity_agent.core.tables.adapters.csv_table import parse_csv_table
from integrity_agent.core.tables.adapters.tsv_table import parse_tsv_table
from integrity_agent.core.tables.adapters.xlsx_table import get_xlsx_sheets, parse_xlsx_sheet
from integrity_agent.core.tables.adapters.markdown_table import parse_markdown_table
from integrity_agent.core.tables.column_profiler import profile_column
from integrity_agent.core.tables.table_schema import TableManifestItem, ColumnProfile

DEFAULT_OUTPUT_DIR = Path("outputs") / "table_intake"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _generate_intake_summary_md(
    path: Path,
    target_dir: Path,
    scanned_files_count: int,
    items: list[TableManifestItem],
) -> None:
    lines = [
        "# Table Intake Summary Report",
        "",
        "## Source package",
        f"- Target folder: `{target_dir.as_posix()}`",
        "",
        "## Statistics",
        f"- Total files scanned: {scanned_files_count}",
        f"- Total tables/sheets extracted: {len(items)}",
        "",
        "## Extracted Tables",
    ]

    if items:
        for item in items:
            sheet_info = f" (Sheet: {item.sheet_name})" if item.sheet_name else ""
            lines.append(
                f"- Table `{item.table_id}` | File: `{item.source_file}`{sheet_info} | "
                f"Format: `{item.source_format}` | Rows: {item.row_count} | Cols: {item.column_count}"
            )
            if item.warnings:
                lines.append(f"  - Warnings: `{', '.join(item.warnings)}`")
    else:
        lines.append("- No tables extracted.")

    lines.extend([
        "",
        "## Limitations",
        "- This intake adapter only processes explicit, local CSV/TSV/XLSX/Markdown files.",
        "- It does not perform OCR on images or extract tables embedded inside PDF documents.",
        "- Complex nested tables, merged cells in spreadsheets, or raw unstructured text are skipped or may fail profiling.",
        "",
        "## Do-not-overclaim notice",
        "- This report surfaces source-data table manifest metadata. It does not determine data fabrication, intent, or research misconduct.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def run_table_intake(
    input_dir: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Execute v0.9 Table Intake scanning on a directory."""
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    resolved_out = DEFAULT_OUTPUT_DIR if output_dir is None else Path(output_dir)
    resolved_out.mkdir(parents=True, exist_ok=True)

    # Scan directory
    scanned_files = sorted(
        [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in [".csv", ".tsv", ".xlsx", ".md"]]
    )

    manifest_items: list[TableManifestItem] = []
    profile_records: list[dict] = []
    table_idx = 1

    # Keep a cache of extracted table data to profile
    # dict: table_id -> (columns, rows_data)
    extracted_data: dict[str, tuple[list[str], list[list[str]]]] = {}

    for file_path in scanned_files:
        ext = file_path.suffix.lower()
        rel_path = file_path.relative_to(input_dir.parent).as_posix()
        src_file = file_path.name

        if ext == ".csv":
            rows, cols, warnings = parse_csv_table(file_path)
            t_id = f"tbl-{table_idx:03d}"
            item = TableManifestItem(
                table_id=t_id,
                source_file=src_file,
                relative_path=rel_path,
                source_format="csv",
                sheet_name=None,
                row_count=len(rows),
                column_count=len(cols),
                columns=cols,
                warnings=warnings,
            )
            manifest_items.append(item)
            extracted_data[t_id] = (cols, rows)
            table_idx += 1

        elif ext == ".tsv":
            rows, cols, warnings = parse_tsv_table(file_path)
            t_id = f"tbl-{table_idx:03d}"
            item = TableManifestItem(
                table_id=t_id,
                source_file=src_file,
                relative_path=rel_path,
                source_format="tsv",
                sheet_name=None,
                row_count=len(rows),
                column_count=len(cols),
                columns=cols,
                warnings=warnings,
            )
            manifest_items.append(item)
            extracted_data[t_id] = (cols, rows)
            table_idx += 1

        elif ext == ".md":
            rows, cols, warnings = parse_markdown_table(file_path)
            if not rows and any("No valid markdown pipe table" in w for w in warnings):
                continue
            t_id = f"tbl-{table_idx:03d}"
            item = TableManifestItem(
                table_id=t_id,
                source_file=src_file,
                relative_path=rel_path,
                source_format="markdown_table",
                sheet_name=None,
                row_count=len(rows),
                column_count=len(cols),
                columns=cols,
                warnings=warnings,
            )
            manifest_items.append(item)
            extracted_data[t_id] = (cols, rows)
            table_idx += 1

        elif ext == ".xlsx":
            sheets = get_xlsx_sheets(file_path)
            # If openpyxl is not installed or error, sheets list is empty
            if not sheets:
                t_id = f"tbl-{table_idx:03d}"
                item = TableManifestItem(
                    table_id=t_id,
                    source_file=src_file,
                    relative_path=rel_path,
                    source_format="xlsx_sheet",
                    sheet_name=None,
                    row_count=0,
                    column_count=0,
                    columns=[],
                    warnings=["Failed to list sheets or openpyxl missing"],
                )
                manifest_items.append(item)
                table_idx += 1
            else:
                for sheet in sheets:
                    rows, cols, warnings = parse_xlsx_sheet(file_path, sheet)
                    t_id = f"tbl-{table_idx:03d}"
                    item = TableManifestItem(
                        table_id=t_id,
                        source_file=src_file,
                        relative_path=rel_path,
                        source_format="xlsx_sheet",
                        sheet_name=sheet,
                        row_count=len(rows),
                        column_count=len(cols),
                        columns=cols,
                        warnings=warnings,
                    )
                    manifest_items.append(item)
                    extracted_data[t_id] = (cols, rows)
                    table_idx += 1

    # Profile columns
    for t_id, (cols, rows) in extracted_data.items():
        # Transpose rows to columns to profile
        col_values: list[list[str]] = [[] for _ in cols]
        for row in rows:
            for col_idx, val in enumerate(row):
                if col_idx < len(col_values):
                    col_values[col_idx].append(val)

        for col_idx, col_name in enumerate(cols):
            vals = col_values[col_idx]
            profile = profile_column(col_name, vals)
            profile_records.append({"table_id": t_id, "profile": profile.to_dict()})

    # Write output files
    manifest_jsonl = resolved_out / "table_manifest.jsonl"
    manifest_csv = resolved_out / "table_manifest.csv"
    profiles_jsonl = resolved_out / "column_profiles.jsonl"
    summary_md = resolved_out / "table_intake_summary.md"

    # 1. Write JSONL manifest
    _write_jsonl(manifest_jsonl, [item.to_dict() for item in manifest_items])

    # 2. Write CSV manifest
    with manifest_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "table_id",
            "source_file",
            "relative_path",
            "source_format",
            "sheet_name",
            "row_count",
            "column_count",
            "columns",
            "warnings",
        ])
        for item in manifest_items:
            writer.writerow([
                item.table_id,
                item.source_file,
                item.relative_path,
                item.source_format,
                item.sheet_name or "",
                item.row_count,
                item.column_count,
                ", ".join(item.columns),
                ", ".join(item.warnings),
            ])

    # 3. Write Column Profiles JSONL
    _write_jsonl(profiles_jsonl, profile_records)

    # 4. Write Summary MD
    _generate_intake_summary_md(summary_md, input_dir, len(scanned_files), manifest_items)

    return manifest_jsonl, manifest_csv, profiles_jsonl, summary_md
