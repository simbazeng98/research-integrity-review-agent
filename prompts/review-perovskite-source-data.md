# Copy-paste prompt: perovskite source-data review

Review the perovskite CSV/TSV/XLSX, J-V/EQE records, PCE table, TRPL/TPV parameters, stability curves, and materials-process lineage that I supply. Offline by default. Run only applicable modules. Never turn PDF/OCR/model extraction directly into a finding.

Admission gate: require an exact source location and `human_confirmed: true`; otherwise keep the item as `evidence_tier: E0` with `eligible_for_finding: false`.

Check, when applicable:

- PCE for the same device, row, scan direction, and mode using the actual illumination; keep scan and stabilized output separate;
- EQE/J-V consistency with area, spectral correction, timing, rounding, and device-identity context;
- TRPL/TPV units and only the explicitly declared amplitude- or intensity-weighted lifetime formula;
- source/plot point coverage from supplied numeric files only, without image digitization;
- non-overlapping curve-segment similarity with guards for smoothing, periodic cycles, sampling, offset/scale, low dynamic range, and instrument quantization;
- quantization, fixed delta, and terminal patterns after excluding IDs, declared derived columns, unit conversions, small samples, rounding, and declared resolution;
- DLS/filtration sample stage and weighting basis as a non-scoring verification question.

For every candidate, report `scope`, source fact, calculation, exact evidence location/hash, `evidence_tier`, `source_version`, `resolution_status`, `counter_evidence`, `safe_report_language`, `do_not_overclaim`, alternative explanations, limitations, and manual verification. Do not hard-code thresholds from a single article. Cap automatic risk at medium.

Separate engineering cost, manufacturability, and scale-up questions and set them outside MRPI. Do not infer motive or responsibility. Report parse counts and distinguish no input, zero findings on valid input, and parse failure.
