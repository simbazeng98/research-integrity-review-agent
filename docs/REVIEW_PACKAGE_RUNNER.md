# Unified Evidence Review Package Runner (introduced in v0.12, updated in v0.2.0)

This domain-agnostic unified runner enables evidence review at a paper or package-level, grouping all standard sub-workflows into a single step-by-step pipeline.

## 1. Overview
The package runner scans a folder-structured package representing a target paper, runs individual checks, tracks their outcomes, and generates consolidated reports.

## 2. Input Structure Requirements
The input folder (e.g. `examples/toy_review_package`) must contain:
- `metadata/`: DOI registry file (`doi.txt`)
- `images/`: Folder of images to review
- `tables/`: Tabular source data files (.csv, .tsv, .xlsx, .md)
- `pv/`: Photovoltaic field data tables
- `raw_pv/`: Unprocessed raw J-V sweeps, EQE spectra, and Excel sheets

The folder can also optionally contain:
- `references/`: Optional references directory. It supports `references/references.txt` (one reference text per line) and `references/references.jsonl` (with reference text and/or DOI attributes).

## 3. CLI Command Usage
To run a unified review on a package folder:
```bash
python -m integrity_agent review-package examples/toy_review_package
```

Options:
- `--skip-images`: Skip image exact duplication and similarity reviews.
- `--skip-tables`: Skip table intake and fixed-delta/terminal-digit reviews.
- `--skip-pv`: Skip PV domain consistency reviews.
- `--skip-raw-pv`: Skip raw PV recalculation, EQE integration, and Excel auditing.
- `--allow-network`: Allow querying Crossref live APIs for updates.
- `-o, --output-dir`: Output directory path (default: `outputs/review_package`).

## 4. Run Execution Loop
The runner executes these stages sequentially:
1. **Intake & DOI Lookup**: Reads DOI metadata, runs status and retraction update reviews (using `status-enrich` workflow to query Crossref, normalize status updates, and extract relation details like type/date/related DOI).
2. **Bibliographic / Reference Scan**: Scans citation metadata for anomalies (missing DOIs, duplicates, malformed DOI patterns, incomplete reference metadata, or offline-resolvable retraction/correction status contexts).
3. **Image Intake & Visual Similarity**: Extracts image dimensions, runs duplicate file checks and perceptual hashing.
4. **Table Intake & Numeric Checks**: Profiles tabular columns, runs fixed delta and terminal digit checks.
5. **PV Domain Consistency**: Rechecks PCE parameters, Voc-loss, tandem matching, and metadata gaps.
6. **PV Evidence Ruleset Completeness**: Performs a completeness audit based on the Photovoltaics (PV) Evidence Ruleset v1 taxonomy over all tabular inputs.
7. **Raw PV Recalculation**: Integrates raw EQE spectra, recalibrates J–V sweeps, and audits Excel workbook cell formulas.
8. **Consolidation**: Bundles findings, outputs a markdown reader summary and static HTML dashboard.

## 5. Output Manifests & Indicators
All execution traces are outputted to the target directory:
- `review_package_manifest.json`: Execution run metadata, parameters, and findings counts.
- `module_status.jsonl`: Module status ledger (success, warning, skipped, failed) containing runtime duration, warnings, error traces, inputs, and outputs.
- `unified_evidence_index.jsonl`: Consolidated database of all candidate signals.
- `review_package_summary.md`: Reader review report.
- `review_package_dashboard.html`: Glassmorphic bento review page.
- `reference_scan/reference_anomalies.jsonl`: Machine-readable reference scan findings.
- `reference_scan/reference_anomaly_summary.md`: Bibliographic reference anomaly summary report.
- `pv_ruleset_review/pv_ruleset_findings.jsonl`: Machine-readable completeness review findings.
- `pv_ruleset_review/pv_ruleset_review_summary.md`: PV Evidence Ruleset completeness review summary report.

## 6. Safety Verdict Boundaries
- **Capped Risk Ceiling**: All findings have risk levels limited to `low` or `medium` (or `high` for retraction/withdrawal status contexts).
- **Neutral Safe Language**: Surfaces candidate signals only. No conclusions or misconduct verdicts are made. Publication status context (such as retractions, corrections, or update notices) is not proof of misconduct. Correction and update notice statuses are mapped to `low` risk.
- **Bibliographic Reference Anomalies**: Identified reference anomalies (missing DOIs, duplicates, malformed patterns, or incomplete citation strings) are bibliographic integrity fingerprints, not proof of misconduct. They represent candidate signals requiring manual verification.
