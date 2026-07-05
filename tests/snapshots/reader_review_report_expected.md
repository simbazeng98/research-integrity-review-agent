# Reader Review Report

## Metadata and source status
- Findings source: `<PROJECT_ROOT>/outputs/rule_findings.jsonl`
- Finding count: 3
- Runtime mode: local toy/stub rule execution.

## Detected risk signals
- `numeric_fixed_delta_between_columns` (medium): Candidate fixed-delta risk signal; verify whether columns are derived, rounded, normalized, or unit-converted.
- `numeric_terminal_digit_anomaly` (medium): Candidate numeric terminal-digit risk signal; requires raw-data and rounding-policy verification.
- `retraction_metadata_check` (medium): Candidate expression of concern metadata signal detected.

## Evidence locations
- `numeric_fixed_delta_between_columns`: examples/toy_rule_package/toy_numeric_fixed_delta.csv at columns reported_a and reported_b; rows 1-5
- `numeric_terminal_digit_anomaly`: examples/toy_rule_package/toy_terminal_digit_anomaly.csv at measurement column; 8/8 terminal digits
- `retraction_metadata_check`: examples/toy_rule_package/toy_metadata_mock.yml at Crossref updates (updated-by)

## Alternative benign explanations
- A unit conversion or normalization step may explain the constant offset.
- Instrument precision or rounding policy may constrain terminal digits.
- Metadata may describe a correction, withdrawal, or context notice rather than article-level misconduct.
- Mock metadata is synthetic and may not correspond to a real DOI.
- The second column may be a disclosed derived value.
- The values may be synthetic, binned, or derived from a formula.

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
- Please explain whether the columns are independent measurements or derived values.
- Please provide raw measurements and the rounding or significant-figure policy.
- Please provide the raw table and formulas used to generate these columns.
- Please verify the notice text from the publisher or authoritative metadata source.

## Limitations
- This detector runs offline by default and requires --allow-network for Crossref queries.
- Toy detector checks only the first two numeric columns in a synthetic CSV.
- Toy detector uses a simple terminal-digit concentration threshold.

## Do-not-overclaim notice
- This report surfaces candidate risk signals for human review. It does not determine misconduct, intent, or responsibility.
