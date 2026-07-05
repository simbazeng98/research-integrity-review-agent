from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.excel_formula_audit import audit_excel_formulas

def test_excel_formula_audit_safety_reject_xlsm():
    # xlsm is rejected for safety
    findings = audit_excel_formulas("examples/toy_raw_pv_package/excel/toy_sheet.xlsm")
    assert len(findings) == 1
    assert findings[0].audit_type == "xlsm_not_supported_for_formula_audit_safety"
    assert findings[0].severity == "medium"

def test_excel_formula_audit_xlsx_content():
    findings = audit_excel_formulas("examples/toy_raw_pv_package/excel/toy_sheet.xlsx")
    
    # Check that we parsed formula cells, volatile function cell, and external reference cell
    audit_types = [f.audit_type for f in findings]
    
    assert "formula_cell" in audit_types
    assert "volatile_function" in audit_types
    assert "external_reference" in audit_types
    assert "hardcoded_output" in audit_types
    assert "formula_overwrite_pattern" in audit_types
    assert "formula_value_mismatch" in audit_types
    
    # Check formula value mismatch coordinate
    mismatch_f = [f for f in findings if f.audit_type == "formula_value_mismatch"]
    assert len(mismatch_f) == 1
    assert mismatch_f[0].cell_coordinate == "C1"
