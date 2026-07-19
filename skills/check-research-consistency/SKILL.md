---
name: check-research-consistency
description: Compare human-confirmed atomic claims and user-supplied CSV, TSV, or XLSX source data across a paper, supplementary information, figures, tables, and publication versions. Use for deterministic recalculation, cross-document consistency, curve-source review, photovoltaic checks, lifetime-fit review, or sample-process lineage questions.
---

# Check Research Consistency

Evaluate only traceable, human-confirmed records. Produce candidate risk signals, alternative explanations, and verification requests—not a truth or conduct verdict.

## Admission gate

Require `human_confirmed: true`, a source location, a source version, and a supplied-file or public-source label. Return unconfirmed items to intake with `eligible_for_finding: false`.

An input `human_confirmed: true` flag is not self-authenticating. Accept it only
when the user explicitly confirms that record in the current request or the
record carries traceable confirmation provenance. Otherwise reset it to false
and return it to intake.

Compare cross-document claims only when this key is complete and matches:

```text
claim_type + device_variant + sample_id + measurement_context + source_version
```

Missing context produces a non-scoring clarification question. It does not produce a contradiction finding.

## Method routing

- Use only supplied CSV, TSV, or XLSX for table and curve calculations. Never digitize a plotted image automatically.
- Recalculate photovoltaic efficiency using the recorded illumination and the same device, row, scan direction, and measurement mode. Keep scan and stabilized values separate.
- Compare EQE and J-V only after checking area basis, timing, spectral correction, and device identity.
- Recalculate TRPL or TPV averages only when the source declares amplitude-weighted or intensity-weighted formulas. Otherwise report a non-scoring formula ambiguity.
- Evaluate quantization, repeated segments, terminal digits, and fixed deltas against sample size, declared resolution, rounding, normalized or derived columns, unit conversions, IDs, smoothing, periodicity, and low dynamic range.
- Treat DLS, filtration, processing order, cost, and manufacturability as sample-stage or engineering questions unless a traceable integrity claim exists. Set `mrpi_eligible: false` for engineering scope.

Read [references/method-recipes.md](references/method-recipes.md) when one of these calculations is requested.

## Candidate record contract

Emit every candidate with all of these fields:

```yaml
finding_id: candidate-id
scope: research_integrity
finding_category: cross_document_or_numeric_or_measurement
rule_id: stable-rule-id
method_family: correlation-family
risk_level: low_or_medium
source_fact: directly observed source statement
detector_or_recomputation_result: bounded calculation result
evidence:
  - source: relative_or_public_label
    location: page_figure_table_or_row
    hash: not_available_or_real_hash
evidence_tier: E1_or_E2_or_E3_or_E4
source_version: explicit-version
resolution_status: open
counter_evidence: []
open_for_scoring: true
mrpi_eligible: true
correlation_group: source_table_method_family
human_confirmed: true
manual_verification: []
false_positive_risks: []
alternative_explanations: []
limitations: []
safe_report_language: Candidate consistency signal requiring source review.
do_not_overclaim: The observation does not establish mechanism, intent, or responsibility.
```

Cap automatic risk at `medium`. A visually striking pattern without measurement context stays `low` or becomes a question only.

## Evidence and version state

- `E1`: confirmed visible source fact.
- `E2`: deterministic recomputation under explicit assumptions.
- `E3`: independently compared supplied source data or current publisher version.
- `E4`: formal publisher or institutional status evidence, reported only in its original scope.

Treat an author response as `counter_evidence` and at most `partially_explained`. Use `resolved_by_version` only when a matching current publisher version addresses the same claim. Use `formally_corrected` only for a formal publisher correction or equivalent authoritative record. Preserve closed history but set `open_for_scoring: false`.

A manifest event alone is navigation metadata, not proof that the current
publisher version resolves a claim. Require the matching publisher artifact,
exact location, visible replacement value or wording, version label, and hash
status before using `resolved_by_version`.

Group signals from the same source, table, and `method_family` into one `correlation_group`. Do not add correlated signals repeatedly. Keep `engineering_plausibility` outside the research-integrity score and reject `unsupported_motive` from public findings.

## Final checks

- Show source facts separately from detector or recomputation results.
- Include `counter_evidence`, benign alternatives, missing evidence, and manual verification for every candidate.
- Mark parse failures and zero-row supplied inputs as `warning` or `failed`, not empty success.
- Refuse to publish records containing private paths, authentication material, unverifiable source anchors, or accusatory conclusions.
