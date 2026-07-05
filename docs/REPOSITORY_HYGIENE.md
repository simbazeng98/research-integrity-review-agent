# Repository Hygiene

This project is designed to be publishable without exposing private research
materials, copyrighted article packages, or unverified personal claims.

## Do Not Commit

- Complete Bilibili or other video transcripts.
- Real paper PDFs or full article text.
- Real supplementary information packages unless their license clearly permits
  redistribution.
- Real source data copied from a paper, lab, reviewer package, or private
  correspondence.
- Unverified personal accusations or private identity details.
- Private emails, chat logs, reviewer messages, or institutional communications.
- Any API token, account credential, private upload key, or secret.

## Allowed In The Public Repo

- Synthetic toy CSV/YAML data under `examples/`.
- Short structured case-card summaries with public source links.
- Detector rule drafts that describe risk signals, false-positive risks, and
  manual-verification needs.
- Reports generated from toy fixtures.

## Local-Only Working Folders

Use ignored folders such as `private_corpora/`, `private_transcripts/`,
`papers_to_review/`, and `outputs/tmp/` for local analysis material. Before
sharing a branch or archive, re-run the tests and check that no private files
are included.
