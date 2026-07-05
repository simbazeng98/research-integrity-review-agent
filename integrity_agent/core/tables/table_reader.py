from __future__ import annotations

from pathlib import Path
from integrity_agent.core.tables.adapters.csv_table import parse_csv_table
from integrity_agent.core.tables.adapters.tsv_table import parse_tsv_table
from integrity_agent.core.tables.adapters.xlsx_table import parse_xlsx_sheet
from integrity_agent.core.tables.adapters.markdown_table import parse_markdown_table


def read_any_table(
    file_path: Path | str,
    sheet_name: str | None = None,
) -> tuple[list[list[str]], list[str], list[str]]:
    """Read a table from any supported format (CSV, TSV, XLSX, Markdown) and return (rows, columns, warnings)."""
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext == ".csv":
        return parse_csv_table(file_path)
    elif ext == ".tsv":
        return parse_tsv_table(file_path)
    elif ext == ".md":
        return parse_markdown_table(file_path)
    elif ext in [".xlsx", ".xlsm"]:
        return parse_xlsx_sheet(file_path, sheet_name or "Sheet1")

    return [], [], [f"Unsupported format: {ext}"]
