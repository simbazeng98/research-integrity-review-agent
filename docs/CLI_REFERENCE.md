# CLI Reference and Offline Defaults

This project is local-first. Commands run offline by default unless a command exposes `--allow-network` and the operator passes it explicitly.

Generated artifacts default to `outputs/...`. Writing curated artifacts into `knowledge_base/...` requires an explicit `--output`, `--output-dir`, or the curated local-batch script.

| Command | Purpose | Default output | Network default |
|---|---|---|---|
| `run-rules examples/toy_rule_package` | Run toy/stub detector rules | `outputs/rule_findings.jsonl` | Offline; `--allow-network` exists for metadata rules only |
| `validate-ledger <findings.jsonl>` | Validate evidence-ledger JSONL schema, safe language, and private-path boundaries | stdout status; optional `--schema-output` writes JSON Schema | Offline |
| `reader-intake --doi <doi>` | Normalize DOI and write paper metadata summary | `outputs/paper_case/` | Offline fixture/stub; `--allow-network` queries Crossref |
| `batch-intake <input>` | Batch DOI/CSL/BibTeX/RIS intake | `outputs/batch_intake/` | Offline fixture/stub; `--allow-network` queries Crossref |
| `status-enrich <input>` | Enrich DOI status with Crossref metadata | `outputs/status_enrich/` | Offline fixture/stub; `--allow-network` queries Crossref |
| `reference-scan <input>` | Scan citations/references for anomalies | `outputs/reference_scan/` | Offline fixture/stub; `--allow-network` queries Crossref |
| `report-batch-html <batch_items.jsonl>` | Render batch intake HTML table | beside/default batch outputs | Offline |
| `image-intake <image_dir>` | Intake local toy image folder and exact duplicate signals | `outputs/image_intake/` | Offline |
| `image-similarity <image_manifest.jsonl>` | Run perceptual image similarity candidates | `outputs/image_intake/` | Offline |
| `report-image-contact-sheet <image_manifest.jsonl>` | Render image contact sheet HTML | `outputs/image_intake/image_contact_sheet.html` | Offline |
| `report-image-similarity-pairs <candidates.jsonl>` | Render visual similarity pair dashboard | `outputs/image_intake/image_similarity_pairs.html` | Offline |
| `table-intake <table_dir>` | Intake CSV/TSV/XLSX/Markdown toy tables | `outputs/table_intake/` | Offline |
| `table-numeric-review <table_manifest.jsonl>` | Run numeric table detectors | `outputs/table_intake/` | Offline |
| `report-table-review-html <table_manifest.jsonl>` | Render table dashboard HTML | `outputs/table_intake/table_review_dashboard.html` | Offline |
| `pv-domain-review <table_manifest.jsonl>` | Run photovoltaic/materials domain checks | `outputs/pv_domain/` | Offline |
| `report-pv-domain-html <pv_findings.jsonl>` | Render PV domain dashboard | `outputs/pv_domain/pv_domain_dashboard.html` | Offline |
| `raw-pv-intake <package_dir>` | Scan raw PV toy package | `outputs/raw_pv/` | Offline |
| `jv-recalculate <jv_folder>` | Recalculate J–V metrics | `outputs/raw_pv/` | Offline |
| `eqe-recalculate <eqe_folder>` | Integrate EQE current density | `outputs/raw_pv/` | Offline |
| `excel-formula-audit <excel_folder>` | Audit Excel formula/hardcoding signals | `outputs/raw_pv/` | Offline |
| `raw-pv-reconcile <package_dir>` | Reconcile raw PV metrics | `outputs/raw_pv/` | Offline |
| `report-raw-pv-html <raw_pv_findings.jsonl>` | Render raw PV dashboard | `outputs/raw_pv/raw_pv_dashboard.html` | Offline |
| `pv-ruleset-export` | Export the PV Evidence Ruleset v1 taxonomy to JSON and MD | `outputs/pv_ruleset_v1/` | Offline |
| `pv-ruleset-review <input>` | Run photovoltaics and materials evidence ruleset completeness review | `outputs/pv_ruleset_review/` | Offline |
| `review-package examples/toy_review_package` | Run unified evidence package runner | `outputs/review_package/` | Offline; `--allow-network` only for metadata checks |
| `report-review-package-html <unified_evidence_index.jsonl>` | Render unified review dashboard | `outputs/review_package/review_package_dashboard.html` | Offline |
| `graph-export <unified_evidence_index.jsonl>` | Export a provenance graph of nodes and edges | `outputs/graph_export/` | Offline |
| `init-package <package_dir>` | Initialize a local review package directory structure | None | Offline |
| `run-audit <package_dir> [--allow-network]` | Run comprehensive integrity audit on a local package | `outputs/review_package/` | Offline; `--allow-network` only for metadata checks |
| `validate-report <findings.jsonl>` | Validate a generated findings ledger file and check basic output presence | stdout status | Offline |
| `wizard` | Guided bilingual onboarding wizard for reviewing a package | `outputs/review_package/` | Offline |
| `view <output_dir>` | Local-only web server to serve and view HTML dashboards | Web browser auto-open | Offline |
| `geng-video-index <seed_urls>` | Build safe Geng video index | `outputs/geng_video_distillation/geng_video_index.yml` | Offline fixture by default; private cache writes require explicit `--write-private-cache` and non-fixture metadata |
| `geng-video-distill <index.yml>` | Distill indexed videos into public-safe case cards | `outputs/geng_video_distillation/cases/` | Offline; reads only configured local private root |
| `geng-video-verify <case_dir>` | Alias for Geng case-card safety validation | stdout status | Offline |
| `geng-video-safety-check <case_dir>` | Validate Geng case-card safety boundaries | stdout status | Offline |
| `geng-video-rule-candidates <case_dir>` | Generate detector rule candidate drafts | `outputs/geng_video_distillation/rule_candidates/` | Offline |

## Bilingual Localization and Local Dashboard Options

Version 0.2.0 introduces bilingual localization (`en` and `zh`) and a portable local web viewer:

- `--lang <en|zh>`: Set the locale for CLI wizard prompts, CLI outputs, and generated dashboards/reports.
- `--view`: Optional flag for `review-package`, `report-review-package-html`, and `wizard` commands that automatically spins up a local zero-dependency Python HTTP server and launches the user's default browser to view the interactive dashboard.


## Bilibili / Geng Video Network Boundary

Default:

```bash
python -m integrity_agent geng-video-index private_video_corpora/geng_bilibili/seed_urls.txt
```

This writes the generated index under `outputs/` and does not write fixture transcript/raw-metadata cache files into the private corpus.

Live metadata requires both network flags, and private cache persistence is a separate explicit opt-in:

```bash
python -m integrity_agent geng-video-index private_video_corpora/geng_bilibili/seed_urls.txt --metadata-mode live --allow-network --write-private-cache
```

Do not pass cookies for this workflow. Complete transcripts, raw media, comments, and danmaku stay private/gitignored. Public cards contain only structured method/risk-signal summaries and safe reporting language.

## Curated Knowledge Base Writes

The regular CLI defaults to `outputs/`. To intentionally write curated artifacts into `knowledge_base/`, pass explicit paths, for example:

```bash
python -m integrity_agent geng-video-distill outputs/geng_video_distillation/geng_video_index.yml --output-dir knowledge_base/cases/geng_video_cases
python -m integrity_agent geng-video-rule-candidates knowledge_base/cases/geng_video_cases --output-dir knowledge_base/detector_rule_candidates/geng_video_distilled
```

For a local ASR batch, use the curated script only when local private audio/ASR processing is intended:

```bash
python scripts/distill_local_geng_bilibili_downloads.py path/to/private/local_downloads
```

## Overwrite Behavior

Generated outputs under `outputs/...` are reproducible artifacts and may be overwritten by smoke tests. Workflows do not clear the whole `outputs/` tree. Geng fixture/default indexing does not write transcript/raw-metadata cache files into the private corpus; live/private cache persistence requires explicit `--write-private-cache` and non-fixture metadata.
