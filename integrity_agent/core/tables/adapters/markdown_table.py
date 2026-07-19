from __future__ import annotations

from pathlib import Path


def parse_markdown_table(
    file_path: Path | str,
) -> tuple[list[list[str]], list[str], list[str]]:
    """Parse a Markdown pipe table and return (rows_data, column_headers, warnings)."""
    file_path = Path(file_path)
    warnings: list[str] = []

    if not file_path.exists():
        warnings.append(f"File not found: {file_path}")
        return [], [], warnings

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        warnings.append(f"Failed to read file: {e}")
        return [], [], warnings

    lines = [line.strip() for line in content.splitlines() if line.strip()]

    # Extract lines starting and ending with '|'
    table_lines = [line for line in lines if line.startswith("|") and line.endswith("|")]
    if len(table_lines) < 3:
        warnings.append("No valid markdown pipe table found (minimum 3 lines required).")
        return [], [], warnings

    def split_row(row_str: str) -> list[str]:
        # Strip outer pipes
        inner = row_str[1:-1]
        return [cell.strip() for cell in inner.split("|")]

    header = split_row(table_lines[0])
    divider = split_row(table_lines[1])

    is_divider = True
    for cell in divider:
        cell_clean = cell.replace(" ", "")
        if not cell_clean:
            continue
        if not all(c in "-:" for c in cell_clean):
            is_divider = False
            break

    if not is_divider:
        warnings.append("Second row of table is not a valid separator line.")
        return [], [], warnings

    rows_data = []
    for idx, line in enumerate(table_lines[2:]):
        row_vals = split_row(line)
        if len(row_vals) != len(header):
            warnings.append(f"Row {idx + 3} has mismatching column count: {line}")
            if len(row_vals) < len(header):
                row_vals += [""] * (len(header) - len(row_vals))
            else:
                row_vals = row_vals[:len(header)]
        rows_data.append(row_vals)

    return rows_data, header, warnings
