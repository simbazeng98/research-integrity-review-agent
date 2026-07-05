# Geng Bilibili Video Distillation Protocol

This protocol covers dry-run distillation of Bilibili videos related to “耿同学学术打假” into safe, structured, reviewable case cards and detector rule candidates.

## Purpose

The goal is **not** to summarize videos or decide whether allegations are true. The goal is to convert public video-raised leads into:

- `video-raised risk signal` records;
- `requires independent verification` questions;
- detector rule candidate drafts;
- public-status tracking tasks.

## Source Hierarchy

1. Formal sources: school/journal/ORI/Crossref/Retraction Watch/court/government notice.
2. Publisher DOI-level correction, retraction, or expression-of-concern pages.
3. PubPeer/public discussion as leads only.
4. Bilibili video narration as allegation/methodology material only.
5. Comments and danmaku as leads only, never fact evidence.

Without a formal source, a case card must use `public_status: allegation` or `public_status: unresolved`. Methodology videos use `public_status: methodology_only` and `case_kind: methodology_note`.

## Private/Public Boundary

Full Bilibili transcripts, ASR outputs, chunk notes, comments, danmaku, screenshots, and raw metadata are private working materials. Public case cards may contain only structured summaries, BV/source URL, risk-signal labels, verification needs, false-positive risks, safe report language, and a redacted private-notes availability flag. Public cards must not contain concrete local private paths.

Private paths:

- `private_video_corpora/geng_bilibili/raw_metadata/`
- `private_video_corpora/geng_bilibili/private_transcripts/`
- `private_video_corpora/geng_bilibili/private_chunk_notes/`
- `private_video_corpora/geng_bilibili/verification_workbench/`

Default generated outputs:

- `outputs/geng_video_distillation/geng_video_index.yml`
- `outputs/geng_video_distillation/cases/`
- `outputs/geng_video_distillation/rule_candidates/`

Curated method-only outputs, produced only by explicit local-batch/curation scripts or explicit `--output` / `--output-dir` choices:

- `knowledge_base/video_index/geng_video_index.yml`
- `knowledge_base/cases/geng_video_cases/`
- `knowledge_base/detector_rule_candidates/geng_video_distilled/`
- `outputs/geng_video_distillation/`

## Dry-Run Workflow

```bash
python -m integrity_agent geng-video-index private_video_corpora/geng_bilibili/seed_urls.txt
python -m integrity_agent geng-video-distill outputs/geng_video_distillation/geng_video_index.yml --dry-run 3
python -m integrity_agent geng-video-safety-check outputs/geng_video_distillation/cases
python -m integrity_agent geng-video-rule-candidates outputs/geng_video_distillation/cases
```

By default these commands stay offline/fixture-based and write generated artifacts under `outputs/geng_video_distillation/`. The default index step does not write fixture transcript/raw-metadata cache files into the private corpus. Writing curated artifacts into `knowledge_base/`, fetching live Bilibili metadata, or persisting live metadata/subtitle cache should be an explicit operator decision, e.g. `--metadata-mode live --allow-network --write-private-cache` plus explicit `--output` / `--output-dir` paths.

The default index step is offline fixture mode. Live Bilibili metadata is allowed only with the explicit pair `--metadata-mode live --allow-network`; it does not request cookies. If no public subtitles are available, transcript confidence is marked metadata-only and ASR is not claimed.

## Chunk Distillation Fields

Private chunk notes should record only working notes:

- paper title / DOI / journal / year when explicitly available;
- figure/table/time marker;
- risk signal type;
- private note on video-displayed evidence;
- whether a formal source is mentioned;
- external verification needed.

Do not copy long transcript excerpts into public YAML.

## Safety Wording

Use “candidate risk signal”, “video-raised concern”, “requires independent verification”, and “public_status”. Do not use verdict-like wording that states a misconduct conclusion as established.

`allegation` cards must include `not independently verified`.
