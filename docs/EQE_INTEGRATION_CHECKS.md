# EQE Spectrum Integration & Verification Checks

This document details External Quantum Efficiency (EQE) spectrum integration methods and discrepancy checks.

## 1. Wavelength-Domain Integration
The short-circuit current density Jsc is computed from the EQE spectrum by integrating the product of EQE and reference solar flux:
`Jsc = (q / (10 * h * c)) * 1e-9 * ∫ EQE(λ) * E(λ) * λ * dλ`
`Jsc = 8.06554e-5 * ∫ EQE(λ) * E(λ) * λ * dλ`

Where:
- `λ` is wavelength in nm.
- `EQE(λ)` is quantum efficiency as a fraction (0 to 1).
- `E(λ)` is AM1.5G spectral irradiance in W/(m² nm).
- Integration is performed using the trapezoidal rule.

## 2. Unit Normalization
- **EQE**: Percent values (0-100) are converted to fraction (divided by 100).
- **Wavelength**: Microns (um) are converted to nanometers (nm) if values are < 10.0.

## 3. Discrepancy Checks
- **Reported Jsc Mismatch**: Compares integrated Jsc with reported EQE Jsc or J-V Jsc.
- **JV Jsc vs EQE Jsc Mismatch**: Mismatch > 10% with absolute difference > 1.0 mA/cm² triggers consistency flags. A 4-5% discrepancy is normal due to calibration differences.

## 4. Warnings and Gaps
- **sparse wavelength grid**: Fewer than 15 data points in the EQE spectrum.
- **measured range narrower than reference range**: Wavelength sweep does not cover the typical 350 nm to 900 nm range.
- **EQE values outside physical range**: Any quantum efficiency values < -0.05 or > 1.05.
- **integrated Jsc unusual high/low**: Recomputed Jsc is < 5.0 mA/cm² or > 50.0 mA/cm².
