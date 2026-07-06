# Release Readiness

## Status

- Version target: v0.2.0 (incorporating v0.12 Unified Evidence Package Runner & v0.2.0 bilingual updates).
- Boundary hardening: P0/P1 audit fix pass completed before this P2 cleanup.
- P2 scope: dead-reference cleanup, CLI/docs consistency, privacy/path regressions, detector-rule registry checks, warning reduction, and release documentation.
- Current release posture: local-first research-integrity evidence review toolkit, not an automatic misconduct adjudicator.

## Supported Input Types

Toy/local inputs currently covered by CLI and tests:

- DOI strings and DOI lists.
- Zotero CSL JSON, BibTeX, and RIS bibliography files.
- Local image folders for exact duplicate and perceptual-similarity candidates.
- CSV, TSV, XLSX, and Markdown tables.
- Photovoltaic/device metric tables and raw PV toy packages.
- Raw J–V sweeps, EQE spectra, reported metric CSVs, and Excel workbooks.
- Geng/Bilibili video indexes and local curated method-only case-card batches.
- Unified review packages under `examples/toy_review_package`.

## Default Offline Principle

- No cloud service is used by default.
- `reader-intake`, `batch-intake`, `run-rules`, and `review-package` remain offline unless `--allow-network` is explicitly passed.
- `geng-video-index` defaults to `--metadata-mode fixture`.
- Fixture/default Geng indexing does not write transcript/raw-metadata cache files into the private corpus.
- Live Bilibili metadata requires `--metadata-mode live --allow-network`; private cache persistence additionally requires `--write-private-cache` and non-fixture metadata.
- CLI defaults write generated artifacts to `outputs/...`.
- Curated writes into `knowledge_base/...` require explicit `--output`, `--output-dir`, or the local curated batch script.

## Not Supported / Out of Scope

- Automatic misconduct decisions or verdict-like conclusions.
- Uploading manuscripts, raw source data, or private corpora to cloud services.
- Processing real papers or real source data during smoke tests.
- Authenticated Bilibili operations or cookie handling.
- Comments/danmaku/person identifiers as factual evidence.
- Large-scale production deployment, multi-user authorization, or hosted review UI.

## Private Data Rules

- Keep private transcripts, ASR output, raw metadata, comments, danmaku, screenshots, raw figures, real source data, and papers under review out of public outputs.
- `.gitignore` must cover private corpora, real-data folders, caches, binary paper/workbook files, and generated outputs.
- `LOCAL_ONLY_DO_NOT_COMMIT.txt` should exist inside the Geng private corpus root.
- Fixture/default Geng indexing must not write or overwrite local ASR transcript caches or local raw metadata caches.
- Public case cards may contain only structured method/risk-signal summaries, verification needs, false-positive risks, and safe report language.

## Known Limitations

- The rule registry contains implemented rules and draft/manual-only rule specifications; draft rules are not runtime detectors.
- Image similarity uses lightweight perceptual hashing and only produces candidate pairs for human review.
- PV/raw-PV checks depend on toy data conventions and require careful mapping before real-world application.
- Crossref/live metadata paths require explicit network opt-in and may still return incomplete metadata.
- Generated `outputs/...` artifacts are reproducible and may be overwritten by smoke tests.
- This directory is currently not initialized as a git repository; first checkpoint should be done deliberately.

## Recommended First Git Checkpoint Procedure

Follow `docs/GIT_FIRST_CHECKPOINT_GUIDE.md`. Key principles:

1. Review `.gitignore` before staging anything.
2. Run `git status --ignored --short` and inspect ignored/private categories.
3. Stage only code, docs, tests, examples, and curated public knowledge-base files.
4. Do not stage private corpus, real data, caches, transcripts, raw media, or generated outputs.
5. Tag the first safe checkpoint after tests and smoke pass.

## Manual Pre-Commit Checklist

- [ ] `python -m pytest -q` passes.
- [ ] CLI smoke commands in this file or the current release task pass.
- [ ] `geng-video-index --metadata-mode live` without `--allow-network` exits with code 2.
- [ ] Geng safety check passes for curated public case cards.
- [ ] No generated tracker YAML exists for the retired tracker family.
- [ ] Generated Markdown/HTML/JSONL reports do not leak local absolute paths or private corpus paths.
- [ ] Docs and public outputs avoid verdict-like wording and use candidate-signal language.
- [ ] Detector rule registry loads all active rules and implemented targets import successfully.
- [ ] Private corpus sentinel exists.
- [ ] `.test_cache*/` is ignored.

## Commands to Run Before Release

```bash
cd path/to/research-integrity-review-agent

python -m pytest -q

python -m integrity_agent review-package examples/toy_review_package
python -m integrity_agent report-review-package-html outputs/review_package/unified_evidence_index.jsonl
python -m integrity_agent report-reader-review outputs/rule_findings.jsonl

python -m integrity_agent geng-video-index private_video_corpora/geng_bilibili/seed_urls.txt
python -m integrity_agent geng-video-safety-check knowledge_base/cases/geng_video_cases
python -m integrity_agent geng-video-rule-candidates knowledge_base/cases/geng_video_cases
```

Expected network-boundary check:

```bash
python -m integrity_agent geng-video-index private_video_corpora/geng_bilibili/seed_urls.txt --metadata-mode live
# expected: exit 2 unless --allow-network is also provided
```
