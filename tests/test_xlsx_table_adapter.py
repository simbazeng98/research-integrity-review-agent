from __future__ import annotations

from pathlib import Path
import pytest
from integrity_agent.core.tables.adapters.xlsx_table import parse_xlsx_sheet, get_xlsx_sheets


def test_parse_xlsx_sheet(tmp_path):
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl is not installed in the current environment")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SheetTest"
    ws.append(["col_x", "col_y"])
    ws.append([10, 20])
    ws.append([30, 40])
    
    xlsx_file = tmp_path / "test.xlsx"
    wb.save(xlsx_file)
    wb.close()
    
    # Test sheets listing
    sheets = get_xlsx_sheets(xlsx_file)
    assert sheets == ["SheetTest"]
    
    # Test sheet parsing
    rows, cols, warnings = parse_xlsx_sheet(xlsx_file, "SheetTest")
    assert len(warnings) == 0
    assert cols == ["col_x", "col_y"]
    assert rows == [["10", "20"], ["30", "40"]]


def test_xlsm_rejected(tmp_path):
    xlsm_file = tmp_path / "unsafe.xlsm"
    xlsm_file.write_text("dummy", encoding="utf-8")
    
    rows, cols, warnings = parse_xlsx_sheet(xlsm_file, "Sheet1")
    assert len(warnings) == 1
    assert "xlsm_not_supported_for_safety" in warnings[0]
