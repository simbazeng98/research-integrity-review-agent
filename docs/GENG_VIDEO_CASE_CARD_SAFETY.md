# Geng Video Case Card Safety

This document defines the public safety contract for Bilibili-derived case cards.

## Required Public Fields

Each public card in `knowledge_base/cases/geng_video_cases/` must include:

- `case_id`
- `source_type: bilibili_video`
- `source_url`
- `bv_id`
- `video_title`
- `transcript_confidence`
- `case_kind`
- `field`
- `paper_identifiers`
- `public_status`
- `public_status_basis`
- `video_raised_risk_signals`
- `evidence_patterns`
- `detector_candidates`
- `manual_verification_needed`
- `false_positive_risks`
- `safe_report_language`
- `limitations`
- `private_notes_reference`

## Public Status Rules

- Specific or multi-case video without formal external source: `public_status: allegation`.
- Methodology video: `case_kind: methodology_note`, `public_status: methodology_only`.
- `allegation` must include `not independently verified`.
- `confirmed_misconduct` must include `official_or_institutional_source`; otherwise validation fails.
- Bilibili, PubPeer, comments, and danmaku cannot upgrade status.

## Forbidden Public Content

Do not publish:

- full subtitles or ASR transcripts;
- long verbatim transcript excerpts;
- screenshot collections;
- comments/danmaku personal information;
- private source data, real figures, or papers under review;
- original video titles that contain allegation/verdict-like wording;
- statements that use verdict-like wording to assert a misconduct conclusion rather than a candidate signal.

## Validator

Run:

```bash
python -m integrity_agent geng-video-safety-check knowledge_base/cases/geng_video_cases
```

The validator checks required fields, status/limitation rules, forbidden keys, forbidden phrases, title redaction, manual verification fields, false-positive risks, and safe report language.

Passing validation means the YAML is safe to review; it does **not** mean the video-raised risk signal is true.
