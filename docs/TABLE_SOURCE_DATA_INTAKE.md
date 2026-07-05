# Table & Source Data Intake Documentation

This document describes the design, implementation boundaries, and manual verification requirements for the Table & Source Data Intake and Numeric Review subsystem introduced in v0.9.

## Scope of v0.9

The table intake subsystem handles user-supplied structured source data files:
1. **Intake Formats:** CSV, TSV, XLSX sheets, and Markdown pipe tables.
2. **Column Profiling:** Categorizes columns as integer, float, string, or mixed. Evaluates unique counts, missing cell counts, unit suffix hints, decimal-place precision distributions, and terminal significant digits.
3. **Numeric Detector Routing:** Automatically evaluates columns against the `numeric_fixed_delta_between_columns` and `numeric_terminal_digit_anomaly` detectors.
4. **HTML Review Dashboard:** Generates a static table manifest dashboard highlighting dimensions, sheets, and risk signal badges.

## Critical Technical Boundaries & Exclusions

- **No OCR:** The system does not run optical character recognition on scanned pages or figures.
- **No PDF Extraction:** The system does not attempt to locate, extract, or reconstruct tabular grids embedded within PDF text layers.
- **No LLM Table Interpretation:** The profiling is entirely deterministic based on regular expressions and statistics.
- **Not a Verdict of Misconduct:** Numeric signal alerts represent mathematical flags for human inspection. They **do not prove** data fabrication, falsification, or research misconduct.

## Heuristic Limitations & False Positives

### 1. Fixed Delta False Positives
- **Disclosed derived columns:** Columns containing calculated formulas (e.g. `mean = (a+b)/2`) will trigger fixed deltas.
- **Unit conversions:** Converting Celsius to Kelvin or inches to centimeters creates constant offsets or multipliers.
- **Normalization:** Min-max scaling or z-score standardizations.

### 2. Terminal Digit Concentration Skews
- **Small sample sizes:** Datasets with fewer than 15 rows can easily exhibit apparent digit concentrations by pure random chance. When the sample size is under 15, the risk level is automatically downgraded to `low`.
- **Instrument thresholds:** Automated measurement instruments may round all outputs to the nearest decimal step (e.g. ending in `.0` or `.5`), which is completely legitimate.

## Manual Verification Checklist

Numeric flags are candidate alerts requiring manual inspection. Human reviewers must verify:
1. **Raw spreadsheets & spreadsheets formulas:** Evaluate formula paths (`=A2+B2`) to confirm if columns are derived.
2. **Analysis scripts:** Review Python/R/MATLAB scripts used to generate the figures or tables.
3. **Rounding and significant-figure policies:** Review the manuscript's experimental precision guidelines.
4. **Instrument export precision:** Check raw instrument parameter output settings.
