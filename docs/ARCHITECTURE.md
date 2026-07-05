# Architecture

## Boundary

`integrity_agent/core/` is domain-agnostic. It defines evidence, provenance,
risk models, reporting primitives, and intake contracts.

`integrity_agent/domains/` contains field-specific rules, such as photovoltaics,
materials characterization, biomedical image integrity, clinical consistency,
AI/ML benchmark consistency, psychology statistics, and chemistry spectra.

## Data Flow

```text
input package
  -> intake
  -> extraction and normalization
  -> detector candidates
  -> evidence ledger
  -> report and verification checklist
```

## Evidence Ledger

The JSONL ledger is the main artifact. Reports, CSV summaries, contact sheets,
and verification questions are derived from ledger records.

## Detector Contract

Before implementation, each detector should have a spec under
`knowledge_base/detector_rules/` with:

- input requirements
- fields required
- risk signal
- false-positive risks
- manual verification requirements
- traceability requirements
