# Case Distillation Guide

Case cards convert public examples and policy documents into reusable, cautious detector-spec drafts. They preserve the evidence pattern, policy status, and verification questions; they do **not** publish complete copyrighted material or decide misconduct.

## Output Contract

Every case card must support three safe outputs:

- `risk_signal`: what visible pattern might be worth checking.
- `requires_verification`: what original data, metadata, image files, policy notices, or institutional records are still needed.
- `public_status`: what the public source actually establishes.

Do not write verdict-like wording that asserts misconduct as established unless the card is quoting a formal public finding, and even then keep it tied to the source.

## Minimum Fields

```yaml
case_id:
priority:
source_type:
source_url:
field:
public_status:
evidence_patterns:
detector_candidates:
manual_verification_needed:
false_positive_risks:
safe_report_language:
```

`confirmed_misconduct` requires `official_or_institutional_source`. `allegation` requires the limitation `not independently verified`.

## Source-Specific Distillation

### News articles

Use news as discovery and narrative context. Extract only:

1. source URL and title;
2. named public status if the article reports a retraction, settlement, lawsuit, expression of concern, or investigation;
3. evidence pattern categories, not full article text;
4. verification questions that point back to DOI-level notices or official records.

If the article is the only basis for a claim, set `public_status: allegation` unless it reports an accountable body has started an investigation or published a notice.

### ORI case summaries

ORI pages are official institutional/federal anchors. You may use `public_status: confirmed_misconduct` only when the ORI page itself states a finding. Still avoid expanding beyond the official scope: preserve the pattern, affected materials, administrative-action context, and manual verification lessons.

### Retraction Watch

Retraction Watch is useful for discovery, mass-retraction context, and links to notices. Prefer DOI-level publisher notices and Crossref/Retraction Watch metadata for final status. Use:

- `mass_retraction` for publisher-scale clusters;
- `retracted` for article-level publisher notices;
- `settlement_or_legal_resolution` for legal settlements without treating them as misconduct findings.

### Crossref / Retraction metadata

Use metadata to normalize `public_status`, identifiers, and notice URLs. Treat metadata as a routing layer: verify the publisher notice text before reporting details.

### Bilibili videos

Bilibili videos can be used only as allegation-level discovery unless an official/public institutional source is also present.

**Hard rule:** full Bilibili video subtitles/transcripts are local intermediate material only. Do not commit full transcripts to the public repo or knowledge base. Public case cards may store only:

- structured summary;
- source URL;
- short timestamp references if needed;
- evidence-pattern labels;
- manual verification questions;
- safe reporting language.

If a local subtitle file was used, record it in private notes or ignored local outputs, not under `knowledge_base/`.

### PubPeer discussions

PubPeer is post-publication discussion, not an institutional finding. Use it to identify figures/tables and questions. Unless a journal/institution has acted, mark the case `allegation` and include false-positive risks.

## Distillation Steps

1. Identify the strongest public source and whether it is official, publisher metadata, news, video, or discussion.
2. Set `public_status` conservatively.
3. Extract evidence-pattern labels, not full source text.
4. Map each pattern to one or more detector spec drafts.
5. Add manual verification needs and false-positive risks.
6. Write safe report language containing “candidate” or “risk signal.”
7. Run `python -m integrity_agent case-distill path/to/case.yml --output outputs/check.jsonl` to catch missing source URLs, invalid statuses, and unsafe confirmed/allegation handling.
8. Run `python -m pytest` before publishing changes.

## Prohibited Content

- Full video transcripts.
- Full copyrighted article text, figures, or tables.
- Private source data.
- Unverified personal accusations stated as fact.
- Detector outputs phrased as misconduct conclusions.
