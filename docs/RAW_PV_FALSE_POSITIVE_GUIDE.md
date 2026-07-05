# Raw PV & Materials False Positive Guide

Consistency signals surfaced by the recalculation layer are candidates for manual review and do not constitute proof of manipulation. This guide details common benign factors that can trigger these signals.

## 1. J–V Recalculation Discrepancies
- **Interpolation Errors**: Linear interpolation at V = 0 or J = 0 is a simplification. If data points are sparse or noisy, recalculated Voc and Jsc may deviate slightly from polynomial fits.
- **Sign Convention**: If the measurement instrument uses custom coordinate rotations, the power output peak might be misidentified.
- **Active Area Scaling**: The electrode active area might be adjusted slightly between measurement and final publication (e.g. from 0.09 cm² to 0.10 cm²), leading to a systematic scaling discrepancy in current density.

## 2. EQE vs J–V current density Mismatches
- **Spectral Mismatch**: Standard solar simulator spectra drift over time. Small variations in simulator mismatch factors can lead to systematic 5–10% current density differences.
- **Degradation**: Perovskite and organic cells degrade quickly. If EQE was measured days after J–V under differing ambient conditions, Jsc will be lower.
- **Capacitive Hysteresis**: Legitimate high hysteresis can lead to displacement currents during fast J–V sweeps, making J-V Jsc appear higher than steady-state EQE Jsc.

## 3. Excel Formula Audit Warnings
- **Pasted Final Values**: Summary sheets often copy/paste final values from instrument software to save sheet size or simplify layouts.
- **Workbook Exporters**: Instrument software (e.g. Keithley or LabVIEW scripts) often outputs data tables with hardcoded headers and summary values without saving formula syntax.
- **Stale Cached Values**: Third-party spreadsheet libraries (like openpyxl or pandas) write sheet values without updating cached calculations. Opening and saving the workbook in Excel resolves this.
