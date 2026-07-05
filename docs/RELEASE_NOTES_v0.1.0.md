# v0.1.0 Public Release Notes

First public MIT release of Research Integrity Evidence Review Agent.

## Highlights

- Local-first CLI for evidence-ledger oriented research-integrity review.
- Rule runtime, detector registry, and safe reader-report contract.
- DOI/batch metadata intake with offline defaults and explicit network gates.
- Image intake and same-package perceptual similarity candidates.
- Table/source-data intake with numeric detector routing.
- Photovoltaics/materials domain plugin, including raw J-V/EQE recalculation and reconciliation.
- Unified evidence package runner for toy review packages.
- Bilibili-derived methodology cards with public title/path redaction and private transcript boundaries.
- Synthetic benchmark snapshot under `docs/BENCHMARKS.md`.
- GitHub Actions CI for pytest and offline CLI smoke checks.

## Safety Boundary

This release produces risk signals, consistency signals, evidence ledger entries,
verification questions, and limitations. It does not determine research
misconduct, authorship intent, or institutional findings.

The repository intentionally excludes real paper PDFs, real source data, raw
figures, private transcripts, raw Bilibili media, screenshots, comments,
danmaku, and private communications.

## Validation

- `python -m pytest -q`: 197 passed
- Offline CLI smoke checks: rule runtime, image intake/similarity, table numeric
  review, PV domain review, raw PV reconciliation, review package, and
  Geng-video safety check
- Private-path and generated-report forbidden-phrase scans: zero hits

## Benchmark Snapshot

Synthetic fixture counts:

- Rule runtime: 3 rule findings
- Image intake/similarity: 6 image manifest rows, 2 similarity candidates
- Table numeric review: 5 table rows, 5 numeric findings
- PV domain plugin: 9 table rows, 22 PV findings
- Raw PV reconciliation: 13 raw PV findings
- Unified review package: 44 unified evidence records
