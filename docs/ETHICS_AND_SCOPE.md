# Ethics And Scope

## What This Tool Does

- Organizes visible evidence into a JSONL evidence ledger.
- Flags candidate image, numeric, statistical, citation, metadata, and domain
  consistency issues.
- Generates verification questions for authors, journals, reviewers, or readers.
- Separates confirmed metadata from risk signals and missing evidence.

## What This Tool Does Not Do

- It does not determine that misconduct occurred.
- It does not infer intent.
- It does not name or shame authors.
- It does not treat PubPeer comments, videos, blog posts, or social media as
  formal findings.
- It does not upload private manuscripts or source data by default.

## Policy Anchors

- ORI defines research misconduct around fabrication, falsification, and
  plagiarism, while excluding honest error and differences of opinion.
- COPE frames retraction as a way to correct the literature and protect its
  integrity, not as a punishment mechanism.
- Nature Portfolio image policies emphasize minimally processed images,
  availability of unprocessed data, and transparent image handling.

These anchors support cautious reporting language: "candidate risk signal" and
"needs manual verification" are preferred over accusations.

## Scope Firewall

Every new review item must declare one of these explicit scopes. The runtime
does not infer scope from words in a title, summary, file name, or comment.

- `research_integrity`: arithmetic, source-data, image, provenance, reporting,
  or cross-document consistency. These candidate signals may contribute to the
  Manual Review Priority Index (MRPI).
- `engineering_plausibility`: cost, scalability, deposition feasibility,
  supply chain, or industrial value. These are shown as separate engineering
  questions and contribute zero to integrity MRPI.
- `unsupported_motive`: an unsupported assertion about intent, concealment, or
  deception. This scope is not a valid evidence-ledger finding and is omitted
  from public reports.

Records created before the scope field was introduced remain readable and
default to `research_integrity`. Producers of new records are responsible for
setting the scope explicitly.
