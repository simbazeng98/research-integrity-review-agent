# Project Instructions

This repository is an independent Research Integrity Evidence Review Agent.

## Scope

- Build local, file-system-first tools for evidence review of research papers.
- Report risk signals, evidence ledger entries, verification questions, and limitations.
- Do not state or imply that the tool determines research misconduct.
- Do not upload user papers or source data to external services by default.
- Use toy data for examples and tests unless a user explicitly supplies public, reusable material.

## Safety Language

- Prefer "risk signal", "candidate", "needs manual review", and "verification request".
- Avoid "fraud", "fake", "misconduct proven", or direct accusations unless quoting a formal public finding.
- Every high-risk finding must include alternative benign explanations and missing evidence.

## Development

- Keep core logic domain-agnostic. Domain-specific rules belong under `integrity_agent/domains/`.
- All findings must be traceable to an input file, DOI metadata, page, figure, table, or data row.
- Add or update tests before changing detector behavior.
