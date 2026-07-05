from __future__ import annotations

import csv
from pathlib import Path


def parse_csv_table(
    file_path: Path | str,
) -> tuple[list[list[str]], list[str], list[str]]:
    """Parse a CSV file and return (rows_data, column_headers, warnings)."""
    file_path = Path(file_path)
    warnings: list[str] = []
    rows_data: list[list[str]] = []
    columns: list[str] = []

    if not file_path.exists():
        warnings.append(f"File not found: {file_path}")
        return [], [], warnings

    # Try reading with utf-8, fallback to latin-1
    content = ""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="latin-1")
            warnings.append("Unicode decode failed for UTF-8; fell back to latin-1.")
        except Exception as e:
            warnings.append(f"Failed to read file: {e}")
            return [], [], warnings
    except Exception as e:
        warnings.append(f"Failed to read file: {e}")
        return [], [], warnings

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        warnings.append("Empty CSV file.")
        return [], [], warnings

    try:
        reader = csv.reader(lines)
        all_rows = list(reader)
        if not all_rows:
            warnings.append("No tabular rows found.")
            return [], [], warnings

        columns = [c.strip() for c in all_rows[0]]
        for r in all_rows[1:]:
            rows_data.append([val.strip() for val in r])
    except Exception as e:
        warnings.append(f"CSV parsing error: {e}")

    return rows_data, columns, warnings
