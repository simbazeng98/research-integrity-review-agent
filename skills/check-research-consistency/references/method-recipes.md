# Method recipes

Load only the section needed for the supplied evidence.

## Photovoltaic efficiency

Use matched values from one device, row, scan direction, and mode:

```text
PCE (%) = Voc (V) * Jsc (mA cm^-2) * FF * 100 / Pin (mW cm^-2)
```

Use the actual `Pin`. If illumination is present but unparseable, stop the calculation. Treat hidden precision, rounding, device mismatch, area basis, scan direction, and stabilized-versus-scan provenance as alternatives.

## TRPL and TPV averages

For `I(t) = sum(A_i * exp(-t / tau_i))`, use only the formula declared by the source:

```text
amplitude weighted = sum(A_i * tau_i) / sum(A_i)
intensity weighted = sum(A_i * tau_i^2) / sum(A_i * tau_i)
```

Normalize units before comparison. If the weighting convention is not declared, report ambiguity without selecting a formula.

## Cross-document claims

Compare a complete identity key only. Keep text, numeric value, unit, source location, and version separate. A different device variant, sample stage, or publication version is a non-match until a human confirms equivalence.

## Quantization and terminal patterns

Record sample count, unique-value ratio, displayed precision, smallest observed step, grid residual, declared instrument resolution, and derived-column status. Do not derive a threshold from one article. Suppress or downgrade IDs, conversions, rounded displays, normalized series, small samples, and patterns explained by declared resolution.

## Curve source coverage and segment similarity

Use supplied numeric source arrays only. Do not infer points from images. For segment similarity, report both non-overlapping ranges, window length, transformation used, similarity metric, dynamic range, and source hash. Suppress constant, near-linear, low-dynamic-range, overlapping, or too-short windows. Consider smoothing, periodic response, repeated protocol cycles, sampling, offset or scale transforms, and instrument quantization as alternatives.

## Materials process lineage

Map each measurement and process step to `sample_id`, stage, time, and weighting basis. DLS-versus-filtration observations normally generate a sample-stage question, not a physical-impossibility statement or integrity score.
