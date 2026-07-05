# Excel Spreadsheet Formula Auditing Guidelines

This document details the checks performed by the Excel formula auditor in v0.11.

## 1. Sheet Structure and Visibility
- **Hidden Sheets**: Checks if the sheet visibility state is not "visible".
- **Hidden Rows/Columns**: Identifies rows or columns flagged as hidden in dimensions.

## 2. Hardcoded Values in Formula Columns
- **Hardcoded Cell Detection**: Flags numeric cells in rows or columns that are otherwise populated by formula cells.
- **Formula Overwrite Pattern**: Flags hardcoded numeric cells located under column headers containing keywords like PCE, efficiency, calculated, or recomputed.

## 3. Simple Formula Evaluator
- Evaluates basic mathematical formulas containing cells and arithmetic operators (`+`, `-`, `*`, `/`, and parentheses).
- Compares evaluated results with cached cell values in the workbook.
- Flags mismatches if the difference exceeds absolute 0.05 or relative 5%.

## 4. Warnings and Volatile Functions
- **xlsm_not_supported_for_formula_audit_safety**: Macro-enabled workbooks (.xlsm) are rejected to prevent macro execution risks.
- **external_reference**: Identifies formulas containing brackets `[` or `]` indicating external file links.
- **volatile_function**: Identifies formulas containing volatile functions (`NOW`, `RAND`, `RANDBETWEEN`, `OFFSET`, `INDIRECT`) that update dynamically.

## 5. Cached Values Caution
- Excel workbooks save the "cached value" of the last calculation. If calculations are disabled or the workbook was written by third-party software, cached values may be blank or stale.
