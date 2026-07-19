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
- `documents/claims.jsonl`: Human-confirmed atomic claims for deterministic cross-document comparison.
- `documents/version_manifest.yml`: Explicit publication-version events and counter-evidence links.
- `documents/decay_fit_records.jsonl`: Human-confirmed TRPL/TPV fit values and component parameters.
- `documents/curve_reconciliations.yml`: Source-table to plot-table mappings. Table paths must stay package-relative and point to supplied CSV/XLSX files; v1 does not digitize images.
- `documents/materials_process_lineage.yml`: Human-confirmed sample-stage, filtration, and DLS context.

Structured records must explicitly set `human_confirmed`. Draft or unconfirmed records cannot create findings. Public source labels remain package-relative; runtime-only absolute paths used to open local files are not copied into the ledger.

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

The structured `documents/` sidecars are independent review inputs and run when present, including when a legacy table/PV directory is absent. A failed module, malformed child ledger, or invalid final unified ledger makes `review-package` and `run-audit` exit nonzero.

## 4. Run Execution Loop
The runner executes these stages sequentially:
1. **Intake & DOI Lookup**: Reads DOI metadata, runs status and retraction update reviews (using `status-enrich` workflow to query Crossref, normalize status updates, and extract relation details like type/date/related DOI).
2. **Bibliographic / Reference Scan**: Scans citation metadata for anomalies (missing DOIs, duplicates, malformed DOI patterns, incomplete reference metadata, or offline-resolvable retraction/correction status contexts).
3. **Document Claims & Versions**: Validates human-confirmed claims, compares matching claim keys, and preserves publisher-linked resolution state without deleting historical findings.
4. **Structured Domain Reconciliation**: Checks declared TRPL/TPV formulas and units, supplied curve point coverage, and materials process lineage.
5. **Image Intake & Visual Similarity**: Extracts image dimensions, runs duplicate file checks and perceptual hashing.
6. **Table Intake & Numeric Checks**: Profiles tabular columns, runs quantization-grid, fixed-delta, and terminal-digit checks with context controls.
7. **PV Domain Consistency**: Rechecks PCE parameters, Voc-loss, tandem matching, and metadata gaps.
8. **PV Evidence Ruleset Completeness**: Performs a completeness audit based on the Photovoltaics (PV) Evidence Ruleset v1 taxonomy over all tabular inputs.
9. **Raw PV Recalculation**: Integrates raw EQE spectra, recalibrates J–V sweeps, and audits Excel workbook cell formulas.
10. **Consolidation & Gate**: Aggregates every child ledger, fails on malformed input, validates the final unified ledger, then renders reports only from a valid ledger.

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
- `document_claim_intake/`, `cross_document_review/`, and `version_reconciliation/`: Normalized claims, consistency findings, and historical/current-version state.
- `pv_decay_fit_review/`, `curve_reconciliation/`, and `materials_process_lineage/`: Structured domain reconciliation findings and summaries.

Every module status distinguishes `input_artifact_count`, `parsed_row_count`, `finding_count`, and `skip_reason`. This separates no input, parsed input with zero findings, zero-parse warnings, and processing failures.

## 6. Safety Verdict Boundaries
- **Capped Risk Ceiling**: All findings have risk levels limited to `low` or `medium` (or `high` for retraction/withdrawal status contexts).
- **Neutral Safe Language**: Surfaces candidate signals only. No conclusions or misconduct verdicts are made. Publication status context (such as retractions, corrections, or update notices) is not proof of misconduct. Correction and update notice statuses are mapped to `low` risk.
- **Bibliographic Reference Anomalies**: Identified reference anomalies (missing DOIs, duplicates, malformed patterns, or incomplete citation strings) are bibliographic integrity fingerprints, not proof of misconduct. They represent candidate signals requiring manual verification.
- **Scope Firewall**: Engineering-plausibility questions and public method cards contribute zero to integrity MRPI. Unsupported motive assertions are not public findings.
- **Version State**: `resolved_by_version` and `formally_corrected` records remain traceable but are closed for scoring. Author responses can provide counter-evidence or `partially_explained` status; they do not establish a formal correction.
- **Correlation Groups**: Findings sharing the same source, table, and method family/correlation group remain individually visible but contribute one group-level MRPI weight.
- **Runtime Privacy Gate**: Verdict-like phrases, local Windows/UNC/POSIX paths, and authentication/session material are rejected before public report rendering.
- **Required Review Context**: Reports expose source fact, detector/recomputation result, mechanism boundary, verification request, evidence tier, source version, resolution status, counter-evidence, benign alternatives, and a do-not-overclaim warning.
