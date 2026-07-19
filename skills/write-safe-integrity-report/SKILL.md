---
name: write-safe-integrity-report
description: Validate reviewed evidence records and turn them into a traceable, publication-safe research-integrity report with candidate signals, counter-evidence, version state, benign alternatives, verification requests, and explicit limits. Use when a user wants to summarize, audit, publish, or share an evidence review without overstating what the records establish.
---

# Write a Safe Integrity Report

Transform existing reviewed records into a bounded report. Do not discover new facts, raise evidence levels, or infer intent during report writing.

## Publication gate

Block the report and list reasons when any candidate:

- lacks `human_confirmed: true`, a source label, an exact location, or a real/declared hash status;
- relies only on an input confirmation flag without current-user confirmation
  or traceable confirmation provenance;
- came directly from unconfirmed PDF, OCR, image, or model extraction;
- contains a local absolute path, authentication material, private correspondence, full social content, or personal data;
- mixes `engineering_plausibility` into research-integrity scoring;
- uses `unsupported_motive` or presents an allegation as an established conclusion;
- raises `evidence_tier`, `resolution_status`, or risk without matching source support.

Return `publication_safety_gate: blocked` and no public report when the gate fails.

## Record validation

Require these fields before rendering:

```text
finding_id, scope, finding_category, rule_id, method_family, risk_level,
source_fact, detector_or_recomputation_result, evidence, evidence_tier,
source_version, resolution_status, counter_evidence, open_for_scoring,
mrpi_eligible, correlation_group, human_confirmed, manual_verification,
false_positive_risks, alternative_explanations, limitations,
safe_report_language, do_not_overclaim
```

Keep `source_fact` distinct from `detector_or_recomputation_result`. State that neither field establishes mechanism, intent, or responsibility.

## Version and scoring rules

- Preserve author responses as `counter_evidence`; do not treat them as formal closure.
- A manifest event alone cannot close a record. Require the matched publisher
  artifact, exact location, replacement value or wording, version label, and
  hash status before rendering `resolved_by_version`.
- Exclude `resolved_by_version` and `formally_corrected` records from open scoring while retaining their history.
- Correlate records by source, table, and `method_family`; count a `correlation_group` once.
- Set `mrpi_eligible: false` for method cards, engineering questions, and unsupported context.
- If weighting or correlation metadata is incomplete, write `MRPI: not computed` instead of estimating a score.
- Describe MRPI only as review prioritization, never as a probability or verdict.

## Report structure

Use these sections in order:

1. Confirmed metadata.
2. Review coverage and module status.
3. Candidate risk signals.
4. Evidence locations.
5. Counter-evidence and version state.
6. Alternative benign explanations.
7. Missing evidence.
8. Manual verification requests.
9. Engineering plausibility questions outside MRPI.
10. Limitations.
11. Do-not-overclaim notice.
12. Publication safety gate: `pass` or `blocked`.

For each candidate, display `evidence_tier`, `source_version`, `resolution_status`, `counter_evidence`, `safe_report_language`, and `do_not_overclaim` prominently.

## Writing rules

- Prefer "candidate signal," "visible consistency issue," "recalculation difference," "needs manual review," and "verification request."
- Attribute formal status only to the named authoritative source and keep its scope exact.
- Do not name people unless necessary for source attribution and already public in the supplied evidence.
- Do not include full copyrighted source text. Quote only the minimum needed to locate a claim.
- End with the materials not reviewed and the checks that remain manual.
