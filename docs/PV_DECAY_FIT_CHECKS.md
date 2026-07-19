# TRPL/TPV Decay-Fit Consistency Checks

`pv_decay_fit_consistency` is an offline, deterministic check for human-confirmed structured TRPL and TPV fit records. It compares reported average lifetimes with supplied biexponential component parameters only when decay type, sample identity, and source version match.

It does not extract text or values from PDFs, figures, or OCR, and it does not infer why a visible difference exists.

## Supported lifetime units

The unit whitelist is:

- `ns`;
- `us`, `μs`, or `µs`;
- `ms`.

All comparisons are performed in nanoseconds. Unknown, non-finite, zero, or negative lifetime values are rejected rather than guessed.

## Supported average-lifetime formulas

For components with amplitude `Ai` and lifetime `τi`, the checker supports:

- amplitude-weighted: `ΣAiτi / ΣAi`;
- intensity-weighted: `ΣAiτi² / ΣAiτi`.

Both conventions are legitimate when explicitly declared. The checker never compares two correctly computed values from different declared conventions as if one must be wrong.

When the averaging formula is absent or unsupported, the output is a low-risk formula-ambiguity record with `open_for_scoring: false`. Missing same-sample/version parameters are handled the same way. A mismatch candidate is created only after a supported formula is declared and the matching parameters are available; its risk cannot exceed `medium`.

## Structured record

```json
{
  "record_id": "claim-figure-trpl",
  "claim_id": "claim-figure-trpl",
  "decay_type": "trpl",
  "sample_id": "sample-A",
  "source_version": "si-v1",
  "source_document": "figure_annotation",
  "source": "documents/claims.jsonl",
  "location": "Figure 2 annotation",
  "source_hash": "sha256:toy-figure",
  "reported_average": 1.75,
  "reported_unit": "μs",
  "declared_formula": "amplitude_weighted",
  "components": [
    {"amplitude": 1.0, "lifetime": 1.0, "unit": "us"},
    {"amplitude": 3.0, "lifetime": 2.0, "unit": "us"}
  ],
  "human_confirmed": true
}
```

A figure/table record may omit `components` when another `source_parameters`, `source_data`, or `fit_table` record supplies them for exactly the same `decay_type + sample_id + source_version` key.

`human_confirmed` is mandatory and must be explicit. Records marked `false` may remain structured draft candidates but are excluded from all findings; omission is a schema error and is never interpreted as confirmation.

## Offline JSONL workflow wrapper

`run_pv_decay_fit_review(records_path, output_dir)` in `integrity_agent.workflows.pv_domain_review` accepts only structured `.jsonl` records and writes:

- `pv_decay_fit_findings.jsonl`, validated against the evidence-ledger contract before publication;
- `pv_decay_fit_summary.md`, with input/confirmed/draft/finding counts and explicit safety limitations.

An empty JSONL file produces a warning summary and a valid empty ledger. Malformed JSON, schema-invalid records, duplicate record IDs, missing files, and PDF/unstructured inputs raise `PVDecayFitReviewError` and leave no stale wrapper outputs. Input and output paths must differ so stale-output cleanup cannot delete the source record file.

## Evidence and version reconciliation

Every output preserves the report and parameter claim IDs, source labels, locations, hashes, sample identity, and source version. Open mismatch candidates carry `resolution_status: open`, `open_for_scoring: true`, and `mrpi_eligible: true`. This allows a later explicitly linked current-publisher version event to make the old observation historical without deleting it.

Formula/parameter ambiguity records remain non-scoring. Alternative explanations always include the other valid formula convention, unit conversion, rounding, fit-range differences, sample/version mismatch, and revised supplementary material.

## Safety boundary

- Inputs must already be human-confirmed structured records.
- No PDF, image, OCR, or language-model extraction is performed.
- No network access or private corpus is required.
- Findings are candidate consistency signals and manual-verification requests, never verdicts about intent or conduct.
