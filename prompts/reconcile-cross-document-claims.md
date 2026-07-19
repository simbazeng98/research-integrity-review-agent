# Copy-paste prompt: cross-document and version review

Review my human-confirmed atomic claims across the main paper, supplementary information, tables, figures, source data, responses, and publication versions. Offline by default. Never turn PDF/OCR/model extraction directly into a finding.

Compare claims only when `claim_type + device_variant + sample_id + measurement_context + source_version` is complete and matched. If identity or context is missing, create a non-scoring verification question rather than a contradiction candidate. Require `human_confirmed: true` and an exact source location before any finding is eligible.

Keep the original observation and version timeline. Treat an author response only as `counter_evidence` and at most `resolution_status: partially_explained`. A manifest event alone is navigation metadata and cannot close a record. Use `resolved_by_version` only when the matching current publisher artifact, exact location, replacement value or wording, version label, and hash status address the same claim; use `formally_corrected` only when a formal authoritative notice supports it. Closed records remain visible but use `open_for_scoring: false`.

Each candidate must include `scope`, source fact, recomputation result, evidence location/hash, `evidence_tier`, `source_version`, `resolution_status`, `counter_evidence`, `safe_report_language`, `do_not_overclaim`, benign alternatives, limitations, manual verification, scoring eligibility, and correlation group. Correlated signals from one source/table/method family must not be counted repeatedly.

Never infer mechanism, intent, or responsibility. Keep engineering plausibility outside research-integrity scoring and exclude unsupported motive from public findings. If input was supplied but parsing fails or produces zero usable rows unexpectedly, report `warning` or `failed`, not empty success.
