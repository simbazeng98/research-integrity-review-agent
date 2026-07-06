# Research Integrity Evidence Review Agent

[![CI](https://github.com/simbazeng98/research-integrity-review-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/simbazeng98/research-integrity-review-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

Local-first tooling for turning research papers, source data, figures, tables,
metadata, and policy context into a reviewable evidence ledger.

This project is not an automatic misconduct detector. It does not decide that an
author committed fraud or research misconduct. It produces risk signals,
traceable evidence items, alternative benign explanations, missing-evidence
notes, and verification questions for human review.

## What It Produces

```text
Input:  DOI / PDF package / source tables / figures / raw PV measurements
Output: evidence ledger + risk signals + verification questions + reader report
```

Every finding is designed to preserve:

- input provenance;
- rule or workflow ID;
- evidence location;
- manual verification requirements;
- false-positive risks and benign alternatives;
- safe report language.

## Modes

- Self-Audit Mode: helps authors and groups check a paper package before
  submission, reduce false positives, and improve source-data completeness.
- Reader Review Mode: helps readers, reviewers, and research-integrity bloggers
  organize visible risk signals without overclaiming.

## Current Capabilities

- DOI and batch metadata intake, including offline-safe Crossref adapters.
- Rule runtime for detector specs and toy/stub execution.
- Image intake and same-package similarity candidates.
- Table/source-data intake with numeric anomaly routing.
- Reader review report and unified evidence package runner.
- Photovoltaics/materials plugin for PCE, EQE/J-V, Voc loss, stability,
  materials-characterization metadata, tandem checks, and raw PV recalculation.
- Bilibili-derived methodology cards with private transcript boundaries and
  public safe-language validation.

No cloud service is used by default, and user papers are not uploaded.

## Quick Start

```bash
# Install the package locally
python -m pip install -e .

# Run the test suite
python -m pytest -q

# Convert a case note draft into a unified ledger entry
python -m integrity_agent case-distill examples/toy_case.md

# Run the paper-level evidence review package scanner
python -m integrity_agent review-package examples/toy_review_package

# Or run it with bilingual/Chinese output localization
python -m integrity_agent review-package examples/toy_review_package --lang zh

# Serve and open the generated local HTML review dashboard in a browser
python -m integrity_agent view outputs/review_package

# Start the bilingual interactive onboarding wizard
python -m integrity_agent wizard --lang zh
```

The case-distill command writes `outputs/evidence_ledger.jsonl` unless `--output` is
provided. The review-package command writes to `outputs/review_package/` unless
`--output-dir` is provided.

## Toy Benchmark Snapshot

The current benchmark snapshot uses only synthetic fixtures:

| Suite | Input | Observed output |
| --- | --- | --- |
| Rule runtime | `examples/toy_rule_package` | 3 rule findings |
| Image intake + similarity | `examples/toy_image_package/images` | 6 image rows, 2 similarity candidates |
| Table numeric review | `examples/toy_table_package` | 5 table rows, 5 numeric findings |
| PV domain plugin | `examples/toy_pv_package` | 9 table rows, 22 PV findings |
| Raw PV reconciliation | `examples/toy_raw_pv_package` | 13 raw PV findings |
| Unified review package | `examples/toy_review_package` | 44 unified evidence records |

See `docs/BENCHMARKS.md` and
`benchmarks/results/v0.1.0_toy_benchmarks.yml`. These are workflow-contract
benchmarks, not claims about real-world misconduct detection accuracy.

## CLI and Release Docs

- `docs/CLI_REFERENCE.md` lists supported CLI commands, default outputs, and network boundaries.
- `docs/RELEASE_READINESS.md` gives the release readiness checklist (originally created for v0.12 boundary fixes, updated for v0.2.0).
- `docs/GIT_FIRST_CHECKPOINT_GUIDE.md` explains the first git checkpoint procedure. This directory is intentionally not initialized as git by the toolchain.

Default workflows are offline and local-first. `--allow-network` is available only for commands that need explicit metadata lookups. Generated artifacts default to `outputs/...`; writing curated artifacts into `knowledge_base/...` requires explicit paths or a curated script.

## Project Layout

```text
.github/workflows/    CI for pytest and offline CLI smoke checks
benchmarks/           synthetic benchmark result snapshots
docs/                 ethics, architecture, and reporting language
knowledge_base/       cases, policies, detector specs, domain rules
integrity_agent/      CLI, core schema, workflows, detectors, domains
examples/             toy-only examples
tests/                regression tests
outputs/              generated local outputs, ignored by git
papers/               local paper workspaces, ignored by git
```

## Policy Anchors

The repo uses public policy sources as anchors, including ORI's definition of
research misconduct, COPE retraction guidance, Nature Portfolio image integrity
standards, and Crossref Retraction Watch metadata access. See
`knowledge_base/policies/example_policy.yml`.

## Prior Art

This project may learn from tools such as `academic-integrity-skill`,
`Anti-Autoresearch`, `PubPeer Zotero plugin`, and `imagededup`, but it is not a
fork of those projects. The distinguishing goal is a case-driven taxonomy plus
traceable evidence ledger and safe reporting language.

## Safety Boundary

This repository intentionally does not include real paper PDFs, real source
data, complete Bilibili transcripts, screenshots, comments, danmaku, private
notes, or private communications. Public Bilibili-derived cards keep raw titles
and transcripts out of the repo and preserve only method/risk-signal summaries.
