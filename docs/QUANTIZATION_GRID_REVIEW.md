# Quantization-Grid Review

The `measurement_precision_anomaly` detector performs a conservative, offline review of numeric source-table columns. It surfaces a candidate only when repetition and a coarse value lattice remain after accounting for displayed precision, sample size, declared resolution, and explicit normalization context.

It does not infer why a grid exists and does not determine intent. Instrument resolution, export formatting, rounding, normalization, binning, smoothing, shared preprocessing, and small samples are mandatory alternative explanations.

## Inputs

The standalone detector accepts a local CSV through the detector registry or `detect_quantization_grid()`:

- `file_path`: supplied CSV path;
- `value_column`: measurement column to analyze;
- `profile` or `profiles`: optional `ColumnProfile`/mapping. Its `precision_hint` is used directly;
- `declared_resolution`: optional scalar or per-column mapping;
- `comparison_values` or `comparison_column`: optional related series for Jaccard grid overlap;
- `normalized` / `normalization_declared`: explicit normalization context, which caps a candidate at low risk.

When no profile is supplied, the detector calls the existing `profile_column()` helper and uses the resulting `ColumnProfile.precision_hint`. It does not tune thresholds to a filename, journal, post, or individual case.

## Auditable metrics

Each candidate retains:

- total and unique counts plus unique ratio;
- modal value/count/ratio;
- consecutive run lengths and maximum run length;
- minimum and modal positive step;
- candidate lattice step, aligned-value overlap, and mean normalized residual;
- related-series grid overlap, defined as Jaccard overlap of unique numeric values;
- `precision_hint`, step-to-precision ratio, and declared resolution;
- whether the declared resolution explains the candidate lattice.

The lattice search ignores steps indistinguishable from displayed precision. A candidate also needs high lattice alignment and independent repetition support. Fewer than eight numeric observations are suppressed; samples below twenty cannot exceed low risk. Risk never exceeds `medium`.

## Declared resolution and normalization

If a positive declared acquisition/export resolution explains the lattice step or an integer multiple of it, the detector suppresses the candidate. A passed `ColumnProfile.precision_hint` can likewise explain an apparent formatting grid. Explicit normalized series are at most low risk and retain normalization as an alternative explanation.

The declared-resolution toy fixture includes a constant `declared_resolution` column so the standalone detector can exercise this path without network access or private data.

## Safety and limitations

- Only supplied numeric CSV values are processed; there is no image digitization or PDF extraction.
- Evidence output uses a repository-relative source label, or only the filename for external temporary inputs.
- Raw social posts, comments, authentication data, and private paths are outside this workflow.
- Every candidate requests source-data, instrument-resolution, rounding, and preprocessing verification.
