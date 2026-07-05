# Batch Intake Summary Report

## Batch input source
- Source file: `toy_dois.txt`
- Source format: `doi_list`

## Number of items parsed
- Total parsed items: 4

## Number of valid DOIs
- Valid DOIs: 3

## Number of duplicate DOIs
- Duplicate DOIs: 0

## Metadata lookup mode: offline / allow-network
- Mode: `offline`

## Retraction metadata summary
- Retractions detected: 1
  - DOI: `10.0000/toy-retracted` | Title: *Mock Retracted Article*

## Correction / expression of concern summary
- Corrections detected: 1
- Expressions of concern detected: 0
  - [Correction] DOI: `10.0000/toy-corrected` | Title: *Mock Corrected Article*

## Items requiring manual verification
- Total requiring manual review: 3
  - Item `txt-L1` | DOI: `10.0000/toy-retracted` | Reason: Has update status 'retraction'
  - Item `txt-L3` | DOI: `10.0000/toy-corrected` | Reason: Has update status 'correction'
  - Item `txt-L4` | DOI: `invalid-doi-here` | Reason: Invalid/Missing DOI

## Limitations
- The batch parser uses lightweight adapters (regular expressions for BibTeX, standard library for CSL JSON and CSV/TXT).
- Metadata latency or indexing lags on Crossref may result in updates not immediately appearing.
- Offline mode uses static mock data or leaves metadata unchecked.

## Do-not-overclaim notice
- This report surfaces candidate risk signals for human review. It does not determine misconduct, intent, or responsibility.
- A status of `no_known_update` does not prove the paper is reliable.
- A status of `metadata_unavailable` does not imply that the paper is suspicious.
- A correction notice does not imply misconduct.
