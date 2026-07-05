# Raw Photovoltaic & Materials Recalculation Layer (v0.11)

This domain-specific layer enables the research integrity evidence review tool to read and recalculate key photovoltaics metrics from raw instrument measurement files and compare them with published summaries.

## 1. Scope
The recalculation layer checks physical parameters directly from raw measurement data:
- Re-extracts J–V sweep characteristics (Voc, Jsc, FF, PCE).
- Performs trapezoidal integration of External Quantum Efficiency (EQE) spectra.
- Reconciles recomputed values with reported table entries.
- Audits Excel workbooks for formula overwrites, external references, and volatile functions.

## 2. What v0.11 Checks
- **J–V Sweep Interpolation**: Voc and Jsc are calculated via linear interpolation around the zero crossings.
- **MPP and Sign Normalization**: Automatic detection of diode vs PV current direction conventions to calculate maximum power output.
- **Hysteresis Matching**: Forward and reverse sweeps are paired to compute the Hysteresis Index (HI).
- **Wavelength Domain Integration**: Integrates EQE against a reference AM1.5G spectrum using trapezoidal rule.
- **Excel Auditing**: Scans cell formulas, cached values, and flags hardcoded cells in formula columns.
- **Discrepancy Reconciliation**: Cross-compares recomputed metrics with reported values.

## 3. What v0.11 Does Not Check
- Does not run OCR or fit complex diode equations.
- Does not download reference spectra from online databases.
- Does not execute Excel macro scripts or VBS/VBA procedures.
- Does not perform spectral mismatch corrections or optical reflectance adjustments.

## 4. Required Inputs
A raw measurements package folder containing:
- `jv/`: Raw J–V curve sweeps (.csv, .tsv, .txt).
- `eqe/`: Raw EQE spectra (.csv, .tsv, .txt).
- `excel/`: Data spreadsheets (.xlsx).
- `reported/`: Summary CSV files containing published table rows.
- `reference/`: Toy AM1.5G solar irradiance files.

## 5. J–V Raw Curve Assumptions
- Delimiter is comma, tab, semicolon, or whitespace.
- Header contains identifiable synonyms for Voltage and Current/Current Density.
- Units are either standard V/mA/mA_cm2, or converted if active area is provided.

## 6. J–V Metric Extraction Method
- Jsc: Calculated at V = 0 via linear interpolation of the two surrounding points.
- Voc: Calculated at J = 0 via linear interpolation of the two surrounding points.
- Pmp: Peak of `abs(V * J)` across the sweep.
- FF: `Pmp / (Voc * Jsc)`.
- PCE: `(Pmp / Pin) * 100%`.

## 7. Hysteresis Index Limitations
- Forward/reverse sweeps are paired by device name and file naming keywords.
- Mismatch triggers medium findings if `abs_delta_pce > 1.0` or `HI > 0.05`.

## 8. EQE Integration Method
- Uses trapezoidal rule: `Jsc = CONST * ∫ EQE(λ) * E(λ) * λ * dλ`.
- Constant is `8.06554e-5` for wavelength in nm, EQE as fraction, and Irradiance in W/(m² nm).

## 9. AM1.5G Reference Spectrum Requirements
- ASTM G-173-03 should be used for formal reviews. v0.11 embeds a toy fallback spectrum for offline validation.

## 10. Excel Formula Audit Method
- Loads spreadsheets twice to inspect formula strings and cached values. Macro-enabled workbooks (.xlsm) are rejected for safety.

## 11. Source Reconciliation Logic
- Matches devices by ID and flags discrepancies if recalculated Voc, Jsc, FF, or PCE exceed configurable absolute or relative tolerances.

## 12. False Positive Risks
- See [RAW_PV_FALSE_POSITIVE_GUIDE.md](RAW_PV_FALSE_POSITIVE_GUIDE.md).

## 13. Manual Verification Protocol
1. Open original raw sweeps in text editor.
2. Confirm active area mask alignment.
3. Review light source intensity calibration traces.
4. Audits formula cells in original Excel files directly.

## 14. Safe Report Language
All findings use safe, non-verdict language like "Candidate raw/source-data reconciliation signal" or "formula audit signal".

## 15. Future Work
- v0.12 candidate features include raw spectral curve loading for XRD/XPS/PL/Raman and peak position extraction.
