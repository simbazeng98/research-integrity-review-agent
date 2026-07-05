from __future__ import annotations

from pathlib import Path
from integrity_agent.core.tables.adapters.markdown_table import parse_markdown_table


def test_parse_markdown_table(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text(
        "\n".join([
            "| col_a | col_b |",
            "|---|---|",
            "| val1 | val2 |",
            "| val3 | val4 |",
        ]),
        encoding="utf-8"
    )
    
    rows, cols, warnings = parse_markdown_table(md_file)
    assert len(warnings) == 0
    assert cols == ["col_a", "col_b"]
    assert rows == [["val1", "val2"], ["val3", "val4"]]
