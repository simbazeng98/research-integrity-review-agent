# Human-Confirmed Document Claim Intake

`document-claim-intake` is an offline, deterministic intake step for atomic claims that a reviewer has already located in a document. It validates structured JSONL, normalizes compatible units for later comparison, and preserves the supplied evidence location and source hash.

It does not read or extract text from PDF files, images, OCR output, or language-model output. A claim record is not a finding. Downstream checks may only use a record as finding evidence when `human_confirmed` is `true`.

## Package layout

The input is optional. A review package that does not have `documents/` remains valid.

```text
review_package/
  documents/
    claims.jsonl
    version_manifest.yml
```

Only `claims.jsonl` is consumed by this intake command. Paths and source labels stored in repository fixtures must be repository-relative; do not add local absolute paths, paper/SI full text, social authentication data, or raw social posts.

## Claim contract

Each JSONL line is one object with these required keys:

```json
{
  "claim_id": "toy-trpl-main",
  "claim_type": "trpl_fit",
  "value": "1.1702",
  "unit": "μs",
  "device_variant": "wide-bandgap",
  "sample_id": "device-02",
  "measurement_context": "TRPL biexponential average lifetime",
  "source_document": "main",
  "source_version": "publisher-v1",
  "location": "Results, paragraph 4",
  "source_hash": "sha256:toy-main-results-p4",
  "human_confirmed": true
}
```

Allowed `claim_type` values are `anneal_temperature`, `concentration`, `layer_order`, `composition`, `trpl_fit`, `tpv_fit`, `pce`, and `other`. Allowed `source_document` values are `main`, `si`, `figure`, `table`, `source_data`, `response`, and `correction`.

`device_variant` is mandatory and non-empty. `sample_id` and `measurement_context` keys are mandatory but may be `null` when the source genuinely does not provide that context; downstream comparison must then produce a context question rather than assume a match.

The comparison key is always:

```text
claim_type + device_variant + sample_id + measurement_context + source_version
```

## Deterministic normalization

Original `value`, `unit`, `location`, and `source_hash` remain in the normalized record. Separate `normalized_value` and `normalized_unit` fields support deterministic comparison. Current conversions include:

- decay time to `ns` (`ps`, `ns`, `us`/`μs`/`μs`, `ms`, `s`);
- temperature to `degC`;
- compatible mass and molar concentration units;
- PCE fraction or percent to `%`;
- explicit unitless markers to `dimensionless` for composition and layer order.

The workflow does not guess unknown units.

## Run

```bash
python -m integrity_agent document-claim-intake \
  examples/toy_review_package/documents \
  -o outputs/document_claim_intake
```

Outputs:

- `document_claims.jsonl`: validated source fields plus deterministic normalized fields and the full comparison key;
- `document_claim_intake_manifest.json`: counts, warnings, offline/extraction flags, and a runner-ready module-status object.

Records with `human_confirmed: false` are retained only with `record_status: draft_candidate` and `eligible_for_finding: false`. Their presence changes intake status to `warning`; it never creates an evidence-ledger finding.

The manifest records a `medium` risk ceiling for any later non-official consistency signal and supplies conservative report language. Intake itself has `finding_count: 0`.
