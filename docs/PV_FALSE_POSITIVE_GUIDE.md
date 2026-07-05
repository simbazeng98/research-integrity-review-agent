# Photovoltaics & Materials False Positive Guide

Consistency signals surfaced by the v0.10 plugin are candidates for human review and do not constitute proof of data manipulation. This guide outlines common benign factors that can trigger these checks.

## 1. PCE Consistency Check Gaps
- **Rounded Values**: Summary tables often report Voc to 2 decimals, Jsc to 1 decimal, and FF to integer percents. Multiplying rounded values can diverge from the fully precise PCE calculated by instruments.
- **FF Percent vs Fraction**: Mappings may interpret raw values differently (e.g. FF column with value `0.78` vs `78%`).
- **Stabilized PCE vs J-V PCE**: The table might list initial J-V curve parameters (Voc, Jsc, FF) alongside a stabilized PCE measured during MPP tracking, which is naturally lower.
- **Non-1-Sun Illumination**: If the device was measured under indoor lighting or concentration (e.g., 0.1 sun, 10 suns) and this is not captured by column mapping, the standard `PCE = Voc * Jsc * FF` check will fail.

## 2. EQE vs J-V current-density Discrepancies
- **Spectral Mismatch**: Small variations in spectral mismatch factors can lead to systematic 5–10% differences.
- **Device Area Mismatch**: The active area defined by electrodes can differ slightly from the aperture area defined by the mask. If J-V is reported based on active area and EQE on aperture area, Jsc values will mismatch.
- **Hysteresis & Transient Behavior**: Slow-responding cells (e.g., perovskite) may show high J-V currents due to capacitive displacement, whereas the steady-state EQE current is lower.
- **Degradation**: If EQE was measured days after J-V and the device degraded, EQE Jsc will be significantly lower.

## 3. Voc Loss Warnings
- **Bandgap Extraction Methods**: Optical bandgaps extracted from Tauc plots or absorption onset can differ by 0.05–0.1 eV from electronic bandgaps, altering the apparent Voc loss.
- **Novel Materials**: Low-efficiency or new materials can exhibit high recombination rates, causing legitimate high Voc losses (> 0.65 eV) that are not errors.
- **Tandem Devices**: Series-connected tandem cell Voc is the sum of subcell voltages, leading to apparent "negative" Voc loss if compared against a single subcell's bandgap.

## 4. Reporting & Stability Checklist Gaps
- **Manuscript Text / SI**: Missing parameters (scan rate, RH, encapsulation) are commonly described in the paper's methods section or figure captions rather than the source tables.
- **Out of Scope**: The table might not represent solar cell parameters at all (e.g., raw film XRD spectra lists), making the completeness checklists irrelevant.
