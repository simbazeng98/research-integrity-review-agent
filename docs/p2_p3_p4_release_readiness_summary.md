# P2/P3/P4 Release Readiness Summary

This document summarizes the release readiness status of Phase 2 (PV Evidence Ruleset v1), Phase 3 (dashboard/graph export), and Phase 4 (wrapper CLIs).

## 1. Accomplished Tasks

- **P2: PV Evidence Ruleset v1 Taxonomy**: Defined 26 evidence completeness and consistency rules in `integrity_agent/domains/photovoltaics/evidence_ruleset_v1.py` covering J-V reporting, EQE/J-V, Stability, Light Intensity, and Tandem metrics.
- **P2: pv-ruleset-review CLI**: Implemented a standalone CLI to scan tabular directories or package manifests, outputting machine-readable findings and user-friendly summary Markdown reports.
- **P3: Dashboard & Graph Export**: Added a dedicated "PV Evidence Completeness" section to the glassmorphic package HTML dashboard. Implemented the `graph-export` CLI to output provenance nodes and edges.
- **P4: Pipeline Integration**: Integrated the PV ruleset review as a unified stage in the package review runner (`run_review_package`), covering both `tables/` and `pv/` folders with proper output cleanup (no-bleed) on subsequent runs.
- **P4: Wrapper CLIs**: Added `init-package`, `run-audit`, and `validate-report` commands to streamline operations.

## 2. Key Output Files

- Standalone Ruleset Findings: `outputs/verify_pv_ruleset/pv_ruleset_findings.jsonl`
- Standalone Ruleset Summary: `outputs/verify_pv_ruleset/pv_ruleset_review_summary.md`
- Package Review Dashboard: `outputs/verify_review_package/review_package_dashboard.html`
- Package Unified Index: `outputs/verify_review_package/unified_evidence_index.jsonl`
- Provenance Graph Nodes/Edges: `outputs/graph_export/provenance_graph_nodes.jsonl` and `provenance_graph_edges.jsonl`

## 3. Safety Verdict Boundaries

- **Candidate Signals Only**: The tool identifies completeness and metadata consistency gaps. Findings are candidate risk signals for manual verification and do not prove or imply academic or research misconduct.
- **Risk Ceiling**: All completeness and consistency findings are capped at a `medium` risk level. Only retraction/withdrawal publisher status updates are allowed to have `high` risk.
- **Bilingual Safe Language**: Every signal includes alternative benign explanations and missing evidence statements to prevent overclaiming.

## 4. Known Limitations

- **Advisory checklist**: The ruleset acts as a completeness checklist and cannot verify the physical truth of correct measurements without raw data review.
- **Synthetic/Toy Fixtures**: The tests and examples are based on synthetic toy datasets.
- **Raw/Source-Data Review**: A final determination always requires manual review of the original raw/source measurement logs and instrument files.

## 5. Verification Commands and Results

| Command | Expected Result | Actual Result |
|---|---|---|
| `git diff --check` | 0 warnings | exit 0; no whitespace errors; Git may emit LF/CRLF notices on Windows |
| `python -m integrity_agent pv-ruleset-review examples/toy_pv_package -o outputs/verify_pv_ruleset` | Wrote findings & summary | Wrote findings (137 records) & summary |
| `python -m integrity_agent validate-ledger outputs/verify_pv_ruleset/pv_ruleset_findings.jsonl` | Ledger validation passed | Passed (137 records) |
| `python -m integrity_agent review-package examples/toy_review_package -o outputs/verify_review_package` | Runs successfully | Runs successfully |
| Index findings count (`pv_evidence_completeness`) | > 0 | Found 115 findings |
| Risk level ceiling for PV findings | <= medium | Capped at medium |
| Dashboard PV Section | Present | Section present |
| Re-run with empty package | pv_ruleset_review cleaned, count = 0 | Cleaned successfully, count = 0 |
| `init-package` empty run audit | 0 findings | 0 findings |
| Run all tests (`python -m pytest -q`) | All green | 241 passed |
