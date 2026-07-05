# Unified Evidence Review Package Runner (v0.12)

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
1. **Intake & DOI Lookup**: Reads DOI metadata, runs status and retraction update reviews.
2. **Image Intake & Visual Similarity**: Extracts image dimensions, runs duplicate file checks and perceptual hashing.
3. **Table Intake & Numeric Checks**: Profiles tabular columns, runs fixed delta and terminal digit checks.
4. **PV Domain Consistency**: Rechecks PCE parameters, Voc-loss, tandem matching, and metadata gaps.
5. **Raw PV Recalculation**: Integrates raw EQE spectra, recalibrates J–V sweeps, and audits Excel workbook cell formulas.
6. **Consolidation**: Bundles findings, outputs a markdown reader summary and static HTML dashboard.

## 5. Output Manifests & Indicators
All execution traces are outputted to the target directory:
- `review_package_manifest.json`: Execution run metadata, parameters, and findings counts.
- `module_status.jsonl`: Module status ledger (success, warning, skipped, failed) containing runtime duration, warnings, error traces, inputs, and outputs.
- `unified_evidence_index.jsonl`: Consolidated database of all candidate signals.
- `review_package_summary.md`: Reader review report.
- `review_package_dashboard.html`: Glassmorphic bento review page.

## 6. Safety Verdict Boundaries
- **Capped Risk Celing**: All findings have risk levels limited to `low` or `medium`.
- **Neutral Safe Language**: Surfaces candidate signals only. No conclusions or misconduct verdicts are made.
