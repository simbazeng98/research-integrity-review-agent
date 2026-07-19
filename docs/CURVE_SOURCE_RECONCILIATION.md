# Curve Source Reconciliation

This offline workflow supports two bounded checks on supplied numeric tables:

- point coverage between a source-data table and a plot-data table; and
- opt-in segment-shape similarity between two independently labelled curves.

It accepts `.csv` and `.xlsx` files only. It does not digitize plot images,
PDF figures, screenshots, or raster graphics.

## Required structured context

Create a `CurveReconciliationSpec` with:

- source and plot table paths plus public-safe source labels;
- exact x/y column mapping;
- table/sheet location, sample ID, source version, and optional supplied hash;
- any disclosed axis limits, downsampling factor, smoothing, NaN handling, or
  filtering interval.

The workflow computes a local SHA-256 hash. When a hash is supplied, it must
match the table contents or the run fails. Local absolute paths are used only
to read the files and are not copied into the evidence ledger.

```python
from integrity_agent.core.curves import (
    CurveColumnMapping,
    CurveDisclosure,
    CurveReconciliationSpec,
    CurveTableSpec,
)
from integrity_agent.workflows.curve_reconciliation import run_curve_reconciliation

spec = CurveReconciliationSpec(
    source_table=CurveTableSpec(
        path="tables/source.csv",
        source_label="tables/source.csv",
        location="source-data rows 2 onward",
        sample_id="device-A",
        source_version="publisher-v1",
    ),
    plot_table=CurveTableSpec(
        path="tables/plot.csv",
        source_label="tables/plot.csv",
        location="plot-data rows 2 onward",
        sample_id="device-A",
        source_version="publisher-v1",
    ),
    mapping=CurveColumnMapping(
        source_x="voltage",
        source_y="current",
        plot_x="voltage",
        plot_y="current",
        x_axis_kind="voltage",
    ),
    disclosure=CurveDisclosure(downsampling_disclosed=True, downsample_factor=2),
)

ledger_path, summary_path = run_curve_reconciliation(spec)
```

## Opt-in segment-shape review

Segment review is deliberately off by default. Add `segment_similarity` only
after a person has checked that the mapped columns are independently labelled
curves and that the two table locations are correct:

```yaml
reconciliations:
  - source_table:
      path: tables/curve-a.csv
      source_label: tables/curve-a.csv
      location: source-data rows 2 onward
      sample_id: sample-a
      source_version: publisher-v1
    plot_table:
      path: tables/curve-b.csv
      source_label: tables/curve-b.csv
      location: source-data rows 2 onward
      sample_id: sample-b
      source_version: publisher-v1
    mapping:
      source_x: time_s
      source_y: signal
      plot_x: time_s
      plot_y: signal
      x_axis_kind: time
    segment_similarity:
      human_confirmed_independent_curves: true
      minimum_window_points: 8
```

Place the record in `documents/curve_reconciliations.yml` and run the normal
`review-package` command. A qualifying result is a medium-ceiling candidate
requiring manual review. The ledger preserves both file hashes, row and x-axis
spans, window length, affine offset/scale, correlation, normalized RMSE,
source versions, alternative explanations, and do-not-overclaim language.

Constant, near-linear, low-dynamic-range, short, overlapping,
missing-value-bridged, or blank-row-bridged windows are excluded. Original CSV
and worksheet row numbers are preserved in the ledger. Linearity is evaluated against the
actual x axis, x-sampling structure must be compatible, and axis-inverted
signals are not promoted to a medium candidate. The default search budget is
500 finite points per curve and eight seed candidates; larger inputs fail
explicitly so a reviewer can supply a traceable subset or raise the declared
budget. Runtime grows with the declared search space, so increasing the budget
should be a deliberate, reviewed choice. Review smoothing, interpolation,
resampling, periodic acquisition, normalization, shared upstream data,
instrument resolution, and documented offset/scale conversions before any
interpretation.

## Decision boundary

- A disclosed downsampled subset is not reported.
- Source rows with non-finite y-values are not treated as expected plotted points.
- Points outside disclosed or visible axis limits are classified as clipping context.
- Explicitly disclosed filtering intervals are excluded from the unexplained
  interval check. A generic filtering disclosure without intervals produces a
  non-scoring context question instead of silently suppressing all gaps.
- Smoothing is recorded as y-value context; point coverage alone does not test a
  smoothing algorithm.
- A contiguous internal interval lacking an explanation produces only a low,
  non-scoring verification question (`open_for_scoring=false`).
- Missing mapping or mismatched sample/version context produces a mapping question,
  not a claim about what happened to any data.

Every question preserves both table locations, hashes, sample ID, source version,
and the exact column mapping. The output is a review aid and does not determine
intent or research misconduct.
