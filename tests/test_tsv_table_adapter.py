from __future__ import annotations

from pathlib import Path
from integrity_agent.core.tables.adapters.tsv_table import parse_tsv_table


def test_parse_tsv_table(tmp_path):
    tsv_file = tmp_path / "test.tsv"
    tsv_file.write_text("col_a\tcol_b\n1.2\t3.4\n5.6\t7.8\n", encoding="utf-8")
    
    rows, cols, warnings = parse_tsv_table(tsv_file)
    assert len(warnings) == 0
    assert cols == ["col_a", "col_b"]
    assert rows == [["1.2", "3.4"], ["5.6", "7.8"]]
