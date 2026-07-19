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
  -> explicit human confirmation and normalization
  -> deterministic within- and cross-document checks
  -> publication-version reconciliation
  -> scoped evidence ledger candidates
  -> child-ledger aggregation and final validation gate
  -> report and verification checklist
```

## Evidence Ledger

The JSONL ledger is the main artifact. Reports, CSV summaries, contact sheets,
and verification questions are derived from ledger records. The package runner
does not render a new report when the final unified ledger is invalid. The
runtime guard rejects verdict-like language, private absolute paths, and
authentication/session material before a record can be published.

Historical records remain in the ledger. Publisher-linked
`resolved_by_version` and `formally_corrected` states close them for MRPI
scoring; an author response alone can be counter-evidence or
`partially_explained`, but not a formal correction.

## Scope and scoring

`research_integrity`, `engineering_plausibility`, and unsupported motive are
separate scopes. Engineering questions and public method cards contribute zero
to integrity MRPI, while unsupported motive assertions are excluded from public
findings. Correlated findings remain traceable individually, but records with
the same source, table, and method family/correlation group contribute one
group-level weight.

## Structured sidecars

The `documents/` package surface accepts human-confirmed atomic claims,
publication-version events, TRPL/TPV fit records, supplied curve-table mappings,
and materials process-lineage records. Curve reconciliation reads only supplied
CSV/XLSX tables and never digitizes images. Runtime file paths may be absolute
for local I/O, but ledger source labels and user-authored sidecar manifests
stay package-relative.

## Detector Contract

Before implementation, each detector should have a spec under
`knowledge_base/detector_rules/` with:

- input requirements
- fields required
- risk signal
- false-positive risks
- manual verification requirements
- traceability requirements
