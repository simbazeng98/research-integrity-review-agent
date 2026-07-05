# Unified Evidence Index Specification

The Unified Evidence Index (`unified_evidence_index.jsonl`) groups all candidate signals discovered during a review package run into a single queryable file.

## 1. Schema Design
Each entry in the JSON Lines index represents a single finding with the following fields:

| Field | Type | Description |
| :--- | :--- | :--- |
| `finding_id` | String | A unique unified identifier (e.g. `UNIFIED-FIND-001`) |
| `rule_id` | String | Identifier matching a detector spec in `knowledge_base/detector_rules/` |
| `detector_id` | String | Module identifier of the detector code |
| `risk_level` | String | Low, Medium, or High (Capped at `medium` for local runs) |
| `source_file` | String | Name of the source file or path where the discrepancy was found |
| `observed_values` | Dict | Key-value pairs containing values observed in the publication |
| `recomputed_values`| Dict | Key-value pairs containing recalculated or verified baseline values |
| `tolerance` | Dict | Tolerance bounds applied during the consistency check |
| `evidence_items` | List | Detailed trace of location, files, and description of the evidence |
| `safe_report_language` | String | Neutral description of the finding, omitting accusations |
| `alternative_explanations`| List | Possible benign reasons (rounding, instrument shifts, calibrations) |
| `manual_verification` | List | Suggested steps for a human reviewer to follow up |
| `limitations` | List | Known boundaries of the detection algorithm |

## 2. Integrated Modules
The index aggregates findings from:
- Metadata/Crossref Retraction checks (`retraction_metadata_check`)
- Image Exact Duplicate check (`image_exact_duplicate_sha256`)
- Image Perceptual Similarity candidates (`image_perceptual_similarity_candidate`)
- Table Numeric Fixed Delta check (`numeric_fixed_delta_between_columns`)
- Table Numeric Terminal Digit check (`numeric_terminal_digit_anomaly`)
- PV PCE Algebraic check (`pv_pce_consistency`)
- PV EQE vs J–V matching (`pv_eqe_jv_jsc_consistency`)
- PV Voc-loss validation (`pv_voc_loss_consistency`)
- PV completeness gaps (`pv_reporting_completeness`, `pv_stability_reporting_completeness`)
- Tandem current matching (`pv_tandem_current_matching`)
- Materials characterization gaps (`pv_materials_characterization_metadata`)
- Raw J-V recalibrations (`pv_jv_metric_recalculation`)
- Hysteresis pairing scans (`pv_jv_hysteresis_candidate`)
- EQE trapezoidal integration (`pv_eqe_spectrum_integration`)
- Excel workbook formula audits (`pv_excel_formula_audit`)
- Raw reported cross-reconciliations (`pv_source_reconciliation`)

## 3. Deduplication and Reader Report Integration
The final reader report generation parses `unified_evidence_index.jsonl`. To prevent double-writing when compiling:
1. The compiler tracks a set of processed unique identifiers.
2. Identifiers check both explicit `finding_id`s and a composite key `(rule_id, source_file, safe_report_language)`.
3. If an evidence is loaded from both the index and individual module log folders, only one entry is written.
