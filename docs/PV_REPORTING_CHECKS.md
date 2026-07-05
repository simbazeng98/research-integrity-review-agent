# Solar Cells & Materials Reporting Completeness Guidelines

This document details the recommended parameters checked by the v0.10 reporting completeness and stability detectors.

## 1. Device Area Definitions
- **Active Area**: The overlap region of the anode and cathode.
- **Aperture Area**: The area defined by an optical aperture mask placed over the cell.
- **Mask Area**: The physical aperture size.
- **Why it matters**: Jsc and PCE scale inversely with area. Reporting the area definition (active vs aperture) and mask geometry is critical for reproducible Jsc reporting.

## 2. J–V Scan Parameters
- **Scan Direction**: Forward (Jsc to Voc) or Reverse (Voc to Jsc).
- **Scan Rate**: The rate of voltage change (in mV/s or V/s).
- **Hysteresis**: Hysteresis between scan directions is common in perovskites. Both directions and rates must be reported.

## 3. Preconditioning
- **Definition**: Pre-bias voltage, light soaking, or storage conditions prior to measurement.
- **Why it matters**: State transitions can change transient device parameters.

## 4. MPP Tracking & Stabilized Output
- **Maximum Power Point (MPP)**: Continuous tracking of power output under load.
- **Stabilized PCE**: The efficiency measured after stabilizing under illumination.

## 5. EQE/IPCE Integrated Current Density
- **EQE Jsc**: Current density obtained by integrating the External Quantum Efficiency spectrum against standard AM1.5G spectral irradiance.
- **Cross-check**: Must match the J-V simulator-derived Jsc within 5-10% to validate calibration.

## 6. Tandem Subcell Characterization
- **Bias Illumination**: Using colored bias light to saturate one subcell while measuring the other.
- **Bias Voltage**: Voltage applied to isolate subcell responses.

## 7. Light Simulator Calibration
- **Reference Cell**: A calibrated reference diode (often Si or GaAs) used to calibrate simulator irradiance.
- **Spectral Mismatch**: Adjustment factor correcting for simulator spectral divergence from standard AM1.5G.

## 8. Statistics & Sample Size
- **Sample Size**: Number of separate cells fabricated and tested.
- **Metrics**: Reporting of average, standard deviation, and best/champion cell outcomes.

## 9. Stability Testing Conditions
- **ISOS Protocols**: Standardized stress protocols (ISOS-D-1, ISOS-L-1, ISOS-T-1, etc.).
- **Parameters**: Aging duration, temperature, relative humidity, electrical bias, encapsulation, and light source.
