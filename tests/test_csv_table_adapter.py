from __future__ import annotations

from pathlib import Path
from integrity_agent.core.tables.adapters.csv_table import parse_csv_table


def test_parse_csv_table(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("col_a,col_b\n1.2,3.4\n5.6,7.8\n", encoding="utf-8")
    
    rows, cols, warnings = parse_csv_table(csv_file)
    assert len(warnings) == 0
    assert cols == ["col_a", "col_b"]
    assert rows == [["1.2", "3.4"], ["5.6", "7.8"]]


def test_parse_csv_table_nonexistent():
    rows, cols, warnings = parse_csv_table("nonexistent.csv")
    assert len(warnings) == 1
    assert "File not found" in warnings[0]
