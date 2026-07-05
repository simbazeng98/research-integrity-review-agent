# J–V Curve Recalculation Guidelines

This document details the methods used to extract device metrics from raw Current–Voltage (J–V) curves in v0.11.

## 1. Sign Convention
Depending on whether the measurement system records photocurrent as positive or negative, power density is computed as:
- **PV Convention**: `Power = V * J`
- **Diode Convention**: `Power = -V * J`

The tool evaluates both and selects the convention yielding a positive maximum power output, outputting a warning if the diode convention is inferred.

## 2. Metric Extraction via Interpolation
- **Jsc (Short-circuit Current Density)**: Value of J at V = 0. Found by linear interpolation of the two data points bounding V = 0:
  `Jsc = J1 + (0 - V1) * (J2 - J1) / (V2 - V1)`
- **Voc (Open-circuit Voltage)**: Value of V at J = 0. Found by linear interpolation of the two data points bounding J = 0:
  `Voc = V1 + (0 - J1) * (V2 - V1) / (J2 - J1)`
- **Pmp (Maximum Power Output)**: The maximum calculated power density point on the curve.
- **FF (Fill Factor)**: Computed as `Pmp / (Voc * Jsc)`.
- **PCE (Power Conversion Efficiency)**: Computed as `(Pmp / Pin) * 100%`.

## 3. Hysteresis Index (HI)
Hysteresis occurs due to charge accumulation or slow response rates. It is calculated by pairing forward and reverse scans of the same device:
- `HI = (PCE_reverse - PCE_forward) / max(PCE_reverse, PCE_forward)`
- `abs_delta_pce = abs(PCE_reverse - PCE_forward)`

A discrepancy of `abs_delta_pce > 1.0` percentage point or `HI > 0.05` triggers a consistency signal for manual review.

## 4. Warnings and Abnormalities
- **too few points**: Sweep contains fewer than 5 points.
- **no voltage zero crossing**: Sweep does not cross V = 0, Jsc is estimated using the closest point.
- **no current zero crossing**: Sweep does not cross J = 0, Voc is estimated using the closest point.
- **non-monotonic voltage sweep**: Voltages are not strictly ascending or descending.
- **unrealistic metric**: Extracted metrics exceed physical thresholds (Voc > 3V, Jsc > 100 mA/cm², FF > 1.0, PCE > 50%).
