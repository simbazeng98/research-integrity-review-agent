# Reader Review Report

## Metadata and source status
- Findings source: `<PROJECT_ROOT>/outputs/rule_findings.jsonl`
- Finding count: 3
- Runtime mode: local toy/stub rule execution.

## Detected risk signals
- `numeric_fixed_delta_between_columns` (low): Candidate fixed-delta context question: confirm that the columns are nominally independent measurements before integrity scoring.
- `numeric_terminal_digit_anomaly` (low): Candidate numeric terminal-digit consistency signal; verify sample size, column role, instrument precision, and rounding policy before interpretation.
- `retraction_metadata_check` (medium): Candidate expression of concern metadata signal detected.

## Evidence locations
- `numeric_fixed_delta_between_columns`: examples/toy_rule_package/toy_numeric_fixed_delta.csv at columns reported_a and reported_b; rows 1-5
- `numeric_terminal_digit_anomaly`: examples/toy_rule_package/toy_terminal_digit_anomaly.csv at column measurement; 8/8 terminal digits
- `retraction_metadata_check`: examples/toy_rule_package/toy_metadata_mock.yml at Crossref updates (updated-by)

## Alternative benign explanations
- A disclosed formula may derive one column from the other.
- A small sample can show a concentrated terminal digit by chance.
- A small sample can show an exact difference without supporting a scored signal.
- A unit conversion or normalization step may explain the constant difference.
- Instrument precision or a declared rounding policy may constrain terminal digits.
- Metadata may describe a correction, withdrawal, or context notice rather than article-level misconduct.
- Mock metadata is synthetic and may not correspond to a real DOI.
- The columns may not represent nominally independent measurements.
- The values may be binned, normalized, or derived from a disclosed formula.

## Missing verification materials
- Crossref relation metadata
- Retraction Watch database entry when licensed/available
- analysis script
- arXiv withdrawal comment
- author explanation
- formula/derived-column audit
- instrument export precision
- publisher notice text
- raw data
- raw measurements
- rounding/significant-figure policy
- spreadsheet formulas

## Suggested verification questions
- Please clarify whether these values are instrument exports or derived values.
- Please distinguish retraction, correction, withdrawal, and expression of concern.
- Please document whether the columns are nominally independent measurements.
- Please provide raw measurements and the rounding or significant-figure policy.
- Please provide raw table data and any formulas used to generate these columns.
- Please verify the notice text from the publisher or authoritative metadata source.

## Limitations
- A fixed difference does not by itself establish data independence or intent.
- Small samples and declared resolution are retained only as non-scoring context questions.
- Terminal-digit concentration alone does not establish data independence or intent.
- The runtime checks constant differences only; it does not implement a ratio detector.
- This detector runs offline by default and requires --allow-network for Crossref queries.

## Do-not-overclaim notice
- This report surfaces candidate risk signals for human review. It does not determine misconduct, intent, or responsibility.
- The Manual Review Priority Index (MRPI) is an estimated density index of candidate anomalies to help prioritize manual verification. It is NOT a misconduct probability. High priority signals must always be evaluated alongside alternative benign explanations and potential limitations of the detectors.
