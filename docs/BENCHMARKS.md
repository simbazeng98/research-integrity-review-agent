# Benchmarks

This project uses toy and synthetic benchmarks to verify that detectors,
workflows, and report contracts remain executable and traceable. These benchmark
results are **not** claims about misconduct-classification accuracy.

## Benchmark Policy

- All included inputs are toy/synthetic fixtures.
- No real paper PDFs, real source data, private transcripts, screenshots, or
  raw media are required.
- A benchmark finding is a risk/consistency signal with manual-verification
  requirements, not a verdict.
- False-positive control matters more than maximizing the number of findings.

## v0.1.0 Toy Benchmark Snapshot

Run context:

- Date: 2026-07-05
- Commit: `v0.1.0` tag target
- Python: `3.11.15`
- Platform: local Windows checkout

| Suite | Input | Primary command | Observed output |
| --- | --- | --- | --- |
| Rule runtime | `examples/toy_rule_package` | `python -m integrity_agent run-rules examples/toy_rule_package` | 3 rule findings |
| Image intake + similarity | `examples/toy_image_package/images` | `image-intake`, then `image-similarity` | 6 image manifest rows, 2 similarity candidates |
| Table numeric review | `examples/toy_table_package` | `table-intake`, then `table-numeric-review` | 5 table manifest rows, 5 numeric findings |
| PV domain plugin | `examples/toy_pv_package` | `table-intake`, then `pv-domain-review` | 9 table manifest rows, 22 PV findings |
| Raw PV reconciliation | `examples/toy_raw_pv_package` | `python -m integrity_agent raw-pv-reconcile examples/toy_raw_pv_package` | 13 raw PV findings |
| Unified review package | `examples/toy_review_package` | `python -m integrity_agent review-package examples/toy_review_package` | 44 unified evidence records |

Machine-readable results are stored in
`benchmarks/results/v0.1.0_toy_benchmarks.yml`.

## Reproduce Locally

```bash
python -m integrity_agent run-rules examples/toy_rule_package

python -m integrity_agent image-intake examples/toy_image_package/images
python -m integrity_agent image-similarity outputs/image_intake/image_manifest.jsonl

python -m integrity_agent table-intake examples/toy_table_package
python -m integrity_agent table-numeric-review outputs/table_intake/table_manifest.jsonl

python -m integrity_agent table-intake examples/toy_pv_package
python -m integrity_agent pv-domain-review outputs/table_intake/table_manifest.jsonl --column-profiles outputs/table_intake/column_profiles.jsonl

python -m integrity_agent raw-pv-reconcile examples/toy_raw_pv_package
python -m integrity_agent review-package examples/toy_review_package
```

Generated files are written under `outputs/`, which is ignored by git.

## Current Limitations

- These benchmarks measure workflow execution and schema contract stability, not
  real-world sensitivity/specificity.
- Image similarity is limited to toy local candidates and does not perform
  all-web image search.
- Numeric and PV findings still require source-data review and benign
  explanation checks before any escalation.
- Public Bilibili-derived cards are methodology-only and keep raw titles,
  transcripts, and chunk notes out of the public repository.
