# Research Integrity Evidence Review Agent

Local-first tooling for turning research papers, source data, figures, tables,
metadata, and policy context into a reviewable evidence ledger.

This project is not an automatic misconduct detector. It does not decide that an
author committed fraud or research misconduct. It produces risk signals,
traceable evidence items, alternative benign explanations, missing-evidence
notes, and verification questions for human review.

## Modes

- Self-Audit Mode: helps authors and groups check a paper package before
  submission, reduce false positives, and improve source-data completeness.
- Reader Review Mode: helps readers, reviewers, and research-integrity bloggers
  organize visible risk signals without overclaiming.

## MVP Boundary

The first version focuses on:

- DOI/PDF/folder intake design.
- Evidence ledger JSONL records.
- Case-to-rule knowledge base.
- Toy case distillation CLI.
- Future image and numeric detectors with explicit manual-review gates.

No cloud service is used by default, and user papers are not uploaded.

## Quick Start

```bash
python -m pytest -q
python -m integrity_agent case-distill examples/toy_case.md
python -m integrity_agent review-package examples/toy_review_package
```

The second command writes `outputs/evidence_ledger.jsonl` unless `--output` is
provided. The review-package command writes to `outputs/review_package/` unless
`--output-dir` is provided.

## CLI and Release Docs

- `docs/CLI_REFERENCE.md` lists supported CLI commands, default outputs, and network boundaries.
- `docs/RELEASE_READINESS.md` gives the v0.12 + boundary-fix release checklist.
- `docs/GIT_FIRST_CHECKPOINT_GUIDE.md` explains the first git checkpoint procedure. This directory is intentionally not initialized as git by the toolchain.

Default workflows are offline and local-first. `--allow-network` is available only for commands that need explicit metadata lookups. Generated artifacts default to `outputs/...`; writing curated artifacts into `knowledge_base/...` requires explicit paths or a curated script.

## Project Layout

```text
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
