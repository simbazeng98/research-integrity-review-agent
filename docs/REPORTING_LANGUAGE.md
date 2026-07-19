# Reporting Language

## Preferred

- "candidate risk signal"
- "visible consistency issue"
- "needs manual review"
- "requires original source data"
- "alternative benign explanation"
- "verification request"

## Avoid

- "fraud"
- "fake"
- "misconduct proven"
- "the authors fabricated"
- "this paper is definitely invalid"

## Report Sections

```text
Confirmed metadata
Detected risk signals
Evidence locations
Alternative benign explanations
Missing evidence
Suggested verification request
Limitations
Do-not-overclaim warning
```

Engineering feasibility questions must appear in a separate
`Engineering plausibility questions (outside integrity MRPI)` section. Do not
describe them as research-integrity findings, and do not use their severity to
increase MRPI.

Unsupported assertions about motive are not public findings. Do not place them
in the evidence ledger, detected-risk section, dashboard, or MRPI input.

Scope is an explicit structured field. Do not classify a record by matching
words such as price, deposition, intent, or concealment in free text.

## Example Verification Question

Please provide the original, unprocessed data used to generate the reported
figure panel and explain how the source data maps to the plotted values.
