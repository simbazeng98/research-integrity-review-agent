# Perovskite Cross-Document Integrity Upgrade Implementation Plan

> Date: 2026-07-11
> Project: repository root
> Baseline: `main` / `a9299b0`, clean working tree before this plan; `python -m pytest -q` → **241 passed in 41.73 s**.
> Evidence basis: a local, read-only analysis package reviewed outside the repository. Only distilled public-method metadata and verification patterns may enter the repository.

## 中文执行摘要

- **前置 P0 blocker**：先修 `review-package` 相对路径静默漏检、PV 字段错误映射、材料表征裸子串误报，以及 case schema 未落实为运行时契约。
- **新增能力第一优先级**：在 blocker 全绿后，建立 `claim × device_variant × sample_id × source_version` 的正文—SI—图表一致性层，并把作者回应、修订 SI、正式勘误纳入状态机。
- **新增能力第二优先级**：把现有 `measurement_precision_anomaly` 从草案升级为带仪器分辨率替代解释的时间序列量化网格 detector。
- **新增能力第三优先级**：新增 TRPL/TPV 单位与拟合公式复算；现有 PCE detector 只补回归测试，不重写。
- **明确拒绝**：不把小红书登录爬虫、供应商价格抓取、动机推断或“量产价值评分”并入核心科研诚信 pipeline。
- **MVP 截止线**：首轮只修 B1–B4，并用真实临时包做端到端回归；第二轮才实施 Tasks 1–6。不要把 bug 修复和 13 个新增任务打成一个 PR。

## Goal

Add a conservative, local-first workflow that can detect and reconcile:

1. main-text/SI/figure/table claim inconsistencies;
2. time-series quantization/repetition patterns;
3. TRPL/TPV fit-value and unit inconsistencies;
4. publication-version drift and author/publisher counter-evidence;
5. scope violations where manufacturability or motive speculation is incorrectly reported as a research-integrity signal.

The upgrade must reuse the existing evidence ledger, PV PCE checker, report-language guard and `review-package` runner. It must **not** become an automatic misconduct detector.

## Non-goals

- Do not embed Xiaohongshu login, scraping, comments, cookies or monitoring in this repository.
- Do not store full copyrighted papers/SI, social-media screenshots, complete comments or authentication tokens in git.
- Do not add vendor-price scraping or infer author motive.
- Do not start with LLM/PDF automatic claim extraction. First prove the deterministic workflow using human-confirmed structured claims.
- Do not tune detector thresholds to reproduce one social-media post.

## Architecture

Introduce an optional local package input:

```text
review_package/
  documents/
    claims.jsonl             # human-confirmed atomic claims
    version_manifest.yml     # source/version/timestamp/status links
```

Each claim is keyed by context, not text alone:

```text
claim_type + device_variant + sample_id + measurement_context + source_version
```

Pipeline:

```text
claim intake
  -> unit/context normalization
  -> cross-document comparison
  -> version/counter-evidence reconciliation
  -> domain checks (PV formula, decay fitting, process lineage)
  -> evidence ledger + safe-language report
```

Risk ceiling remains `medium` for non-official signals. Only formal publisher/institutional status metadata can be reported as formal status; intent is never inferred.

---

## P-1 — Existing correctness blockers (must precede feature work)

以下四项已由独立审计提出，并由主代理在系统临时目录中再次复现；它们不是推测，也不应与新 detector 一起顺手修改。

### B1: Fix package-relative table resolution and forbid silent zero-parse success

**Confirmed symptom**

- A temporary `review-package` containing `pv/metrics.csv` with an obvious PCE mismatch logged `File not found: pv/metrics.csv, skipping.`.
- `pv-domain-review` and `table-numeric-review` still reported `success` while the unified index contained no PCE, fixed-delta, or terminal-digit finding.

**Files**

- Modify: `integrity_agent/workflows/review_package.py`
- Modify: `integrity_agent/workflows/table_numeric_review.py`
- Modify: `integrity_agent/workflows/pv_domain_review.py`
- Modify: `integrity_agent/domains/photovoltaics/schema.py`
- Modify: `integrity_agent/core/packages/package_schema.py`
- Test: `tests/test_review_package_package_relative_paths.py`
- Extend: `tests/test_review_package_pv_ruleset.py`

**Root-cause direction**

- Preserve public manifest paths as relative paths.
- Pass `table_base_dir=pack_path` explicitly and resolve every manifest item against the package root, not `Path.cwd()`.
- A manifest with input artifacts but zero parsed rows must emit `warning` or `failed`, never an empty `success`.
- Extend module status with `input_artifact_count`, `parsed_row_count`, `finding_count`, and an explicit skip/failure reason.

**Acceptance**

1. A `tmp_path/pkg/tables/` fixture sends fixed-delta and terminal-digit findings into `unified_evidence_index.jsonl`.
2. A `tmp_path/pkg/pv/` fixture sends an obvious PCE finding into the same index.
3. No `File not found` warning occurs for valid package-relative files.
4. `validate_ledger_file()` passes.
5. “No input”, “input parsed with zero findings”, and “input failed to parse” are distinct module states.

### B2: Correct PV measurement-context mapping and stop unsafe 1-sun fallback

**Confirmed symptom**

```text
Light intensity (mW/cm2)       -> unmapped
Stability duration (h)         -> t80_h
Stabilized power output (%)    -> stabilized_pce_percent
```

This can turn a correct non-1-sun row into a false PCE inconsistency.

**Files**

- Modify: `integrity_agent/domains/photovoltaics/field_mapping.py`
- Modify: `integrity_agent/domains/photovoltaics/schema.py`
- Modify: `integrity_agent/domains/photovoltaics/units.py`
- Modify: `integrity_agent/domains/photovoltaics/pce_consistency.py`
- Modify: `integrity_agent/domains/photovoltaics/stability_reporting.py`
- Test: `tests/test_pv_measurement_context_mapping.py`
- Extend: `tests/test_pv_pce_consistency.py`
- Extend: `tests/test_pv_stability_reporting.py`

**Acceptance**

1. `80 mW/cm²` and reported PCE `22.6875%` do not produce a false PCE finding.
2. `500 h` maps to `stability_duration_h`, never `t80_h` unless explicitly labelled T80.
3. `Stabilized power output (%)` maps to `stabilized_power_output_percent`.
4. An empty Temperature/RH column does not count as a reported condition.
5. If an illumination header is present but unparsable, the detector emits missing-context/low-risk output instead of silently assuming 100 mW cm⁻².

### B3: Replace bare substring detection in materials characterization

**Confirmed symptom**

`sample_metrics.csv` plus `Temperature (C)` produced both PL/TRPL and SEM/TEM completeness findings because `sample` contains `pl` and `temperature` contains `tem`.

**Files**

- Modify: `integrity_agent/domains/photovoltaics/materials_characterization.py`
- Optionally modify: `integrity_agent/domains/photovoltaics/field_mapping.py`
- Extend: `tests/test_pv_materials_characterization.py`

**Acceptance**

1. `sample_metrics.csv + Temperature (C)` produces zero materials-characterization findings.
2. Explicit tokens/aliases such as `XRD`, `XPS`, `TRPL`, `SEM image`, and `TEM micrograph` still route correctly.
3. File-name inference alone cannot create a finding; at most it creates candidate context.
4. Existing XRD/XPS/PL positive fixtures remain green.

### B4: Turn the case schema and safe-language policy into runtime contracts

**Confirmed symptom**

An incomplete allegation card lacking source URL, evidence patterns, manual verification, and false-positive risks passed `validate_case_card()` with only a warning. A separate unique-string probe confirmed that a valid card's `safe_report_language` is dropped during YAML → `Finding` → ledger conversion; the generic `Finding` schema currently has no such field.

**Files**

- Modify: `knowledge_base/cases/case_schema.yml`
- Modify: `integrity_agent/workflows/case_distill.py`
- Modify: `integrity_agent/workflows/geng_video_distillation.py`
- Modify: `integrity_agent/core/evidence/schema.py` and/or `integrity_agent/core/evidence/ledger_schema.py`
- Modify: `integrity_agent/core/safety.py`
- Test: `tests/test_case_schema_contract.py`
- Extend: `tests/test_case_distill_cli.py`
- Extend: `tests/test_geng_video_case_schema.py`
- Extend: `tests/test_geng_video_safety_validator.py`

**Acceptance**

1. A production card missing required evidence, false-positive, manual-verification, or source/status fields exits non-zero and writes no ledger record.
2. Toy/draft relaxation is explicit, not silently inferred.
3. `safe_report_language` survives YAML → Finding → unified ledger.
4. Generic and Geng-video paths use one shared forbidden-language/private-path contract, with platform-specific extensions only where needed.

**B1–B4 release gate**

```bash
# Run from the repository root.
python -m pytest -q \
  tests/test_review_package_package_relative_paths.py \
  tests/test_pv_measurement_context_mapping.py \
  tests/test_pv_materials_characterization.py \
  tests/test_case_schema_contract.py
python -m pytest -q
```

Do not start the new claim/quantization work until these tests are red first, then green, and the full suite passes.

---

## P0 — Provenance, case state and safety boundary

### Task 1: Distill six public-method cards without importing raw social content

**Files**

- Create: `knowledge_base/cases/perovskite_public_methods/xhs_ne_quantization_grid_2026.yml`
- Create: `knowledge_base/cases/perovskite_public_methods/xhs_ees_cross_document_2026.yml`
- Create: `knowledge_base/cases/perovskite_public_methods/xhs_afm_decay_dls_2026.yml`
- Create: `knowledge_base/cases/perovskite_public_methods/xhs_aem_pce_recalculation_2022.yml`
- Create: `knowledge_base/cases/perovskite_public_methods/xhs_afm_manufacturability_boundary_2026.yml`
- Create: `knowledge_base/cases/perovskite_public_methods/xhs_afm_response_version_drift_2026.yml`
- Test: `tests/test_perovskite_public_method_cards.py`

**Steps**

1. Write a failing parametrized test that loads all six cards with `validate_case_card`.
2. Require `public_status: public_method_example` or `unresolved`; never `confirmed_misconduct`.
3. Store only DOI, source URL + feed_id, access date, brief method summary, evidence patterns, alternative explanations and verification requests.
4. Link the AFM critique card to the response card as counter-evidence.
5. Explicitly mark social claims and commenter identities as not independently verified.
6. Verify no card contains `xsec_token`, Cookie, full post text, complete comments or copied article text.

**Acceptance**

- Six cards validate.
- All paper-specific claims have DOI + source URL + access timestamp.
- Each card has at least two false-positive risks and two manual-verification requests.
- Repository safety tests confirm no raw transcript/social dump was committed.

### Task 2: Extend the case schema with evidence tier and counter-evidence state

**Files**

- Modify: `knowledge_base/cases/case_schema.yml`
- Modify: `integrity_agent/workflows/case_distill.py`
- Test: `tests/test_case_evidence_tier_and_counterevidence.py`
- Modify: `docs/CASE_DISTILLATION_GUIDE.md`

**Optional fields**

```yaml
target_doi: string
source_accessed_at: ISO-8601
source_snapshot_hash: string | null
evidence_tier: E0 | E1 | E2 | E3 | E4
counter_sources:
  - url: string
    source_type: author_response | publisher_update | correction | raw_data_offer | other
    observed_at: ISO-8601
resolution_status: open | partially_explained | resolved_by_version | formally_corrected | unresolved
version_timeline: []
```

**Steps**

1. Add failing validation tests for invalid evidence tiers and missing provenance.
2. Require paper-specific social-method cards to include `target_doi`, `source_accessed_at`, `evidence_tier`, and `resolution_status`.
3. Require any `resolved_by_version`/`formally_corrected` status to cite a counter source.
4. Keep backward compatibility for existing case cards.
5. Surface these fields in distilled ledger provenance.

**Acceptance**

- Existing case-bank tests remain green.
- A social allegation cannot silently become `confirmed_misconduct`.
- Counter-evidence and resolution state survive YAML → ledger conversion.

### Task 3: Add a scope firewall for integrity vs engineering plausibility

**Files**

- Create: `integrity_agent/core/evidence/scope.py`
- Modify: `integrity_agent/core/evidence/ledger_schema.py`
- Modify: `integrity_agent/workflows/report_reader_review.py`
- Modify: `integrity_agent/core/reporting/html_dashboard.py`
- Test: `tests/test_integrity_scope_firewall.py`
- Modify: `docs/ETHICS_AND_SCOPE.md`
- Modify: `docs/REPORTING_LANGUAGE.md`

**Rules**

- `research_integrity`: arithmetic, source-data, image, provenance, reporting or cross-document consistency.
- `engineering_plausibility`: cost, scalability, deposition feasibility, supply chain, industrial value.
- `unsupported_motive`: claims about intent, concealment or deception without an official source; block from public reports.

**Acceptance**

- “High price” and “hard to evaporate” cannot increase integrity risk.
- “Purchased to conceal actual use” is blocked or rendered only as an unsupported social assertion, never as a finding.
- Reports can show engineering questions in a separate section with no MRPI contribution.

---

## P1 — Deterministic cross-document and numeric checks

### Task 4: Add a human-confirmed atomic claim schema and intake workflow

**Files**

- Create: `integrity_agent/core/claims/__init__.py`
- Create: `integrity_agent/core/claims/schema.py`
- Create: `integrity_agent/workflows/document_claim_intake.py`
- Modify: `integrity_agent/core/packages/package_schema.py`
- Modify: `integrity_agent/workflows/review_package.py`
- Modify: `integrity_agent/__main__.py`
- Test: `tests/test_document_claim_schema.py`
- Test: `tests/test_document_claim_intake.py`
- Fixture: `examples/toy_review_package/documents/claims.jsonl`
- Docs: `docs/DOCUMENT_CLAIM_INTAKE.md`

**Minimum claim fields**

```json
{
  "claim_id": "...",
  "claim_type": "anneal_temperature|concentration|layer_order|composition|trpl_fit|tpv_fit|pce|other",
  "value": "...",
  "unit": "...",
  "device_variant": "...",
  "sample_id": "...",
  "measurement_context": "...",
  "source_document": "main|si|figure|table|source_data|response|correction",
  "source_version": "...",
  "location": "...",
  "source_hash": "...",
  "human_confirmed": true
}
```

**Steps**

1. Write schema tests first, including missing `device_variant` and invalid unit cases.
2. Implement JSONL intake with deterministic normalization only.
3. Reject automatic findings from `human_confirmed: false`; allow them only as draft extraction candidates.
4. Add `documents_dir` to `ReviewPackageInput` without breaking existing packages.
5. Emit an intake manifest and warnings into module status.

**Acceptance**

- Existing review packages with no `documents/` directory remain unchanged.
- Claims preserve exact source location and hash.
- No unstructured PDF/LLM extraction occurs in this phase.

### Task 5: Implement context-aware cross-document claim consistency

**Files**

- Create: `integrity_agent/detectors/claims/__init__.py`
- Create: `integrity_agent/detectors/claims/cross_document.py`
- Create: `knowledge_base/detector_rules/cross_document_claim_consistency.yml`
- Create: `integrity_agent/workflows/cross_document_review.py`
- Modify: `integrity_agent/detectors/registry.py`
- Modify: `integrity_agent/workflows/review_package.py`
- Test: `tests/test_cross_document_claim_consistency.py`
- Test: `tests/test_review_package_cross_document.py`

**Comparison contract**

- Compare only claims matching the same `device_variant`, `sample_id` and measurement context.
- Normalize compatible units before comparing.
- Preserve source version and time; never compare stale and revised versions as if simultaneous.
- Output `visible_consistency_issue`, not misconduct language.

**Required test cases**

1. Same device: `2 mg/mL` vs `3 mg/mL` → finding.
2. Different bandgap/device branch → no finding.
3. `1.1702 μs` vs `1170.2 ns` → unit-consistent, no finding.
4. Layer sequences with the same layers but different order → finding.
5. Composition strings with reversed I/Br ratios for the same variant → finding.
6. Main text vs old SI mismatch, followed by revised SI match → status `resolved_by_version`, no open medium finding.
7. Missing sample identity → question/low-confidence record, not a contradiction.

**Acceptance**

- Every finding includes both evidence locations and the exact comparison key.
- False-positive alternatives include variant mismatch, typographical error, stale SI and unit conversion.
- Risk ceiling is `medium`; missing context defaults to `low` or review question.

### Task 6: Add publication version and counter-evidence reconciliation

**Files**

- Create: `integrity_agent/core/claims/version_schema.py`
- Create: `integrity_agent/workflows/version_reconciliation.py`
- Create: `knowledge_base/detector_rules/publication_version_drift.yml`
- Modify: `integrity_agent/workflows/review_package.py`
- Modify: `integrity_agent/workflows/report_reader_review.py`
- Modify: `integrity_agent/core/reporting/html_dashboard.py`
- Test: `tests/test_version_reconciliation.py`
- Fixture: `examples/toy_review_package/documents/version_manifest.yml`

**Source precedence (status, not truth)**

1. publisher correction/retraction/update;
2. current publisher article/SI version;
3. original public version;
4. author response or supplied revised draft;
5. third-party social commentary.

An author response is counter-evidence, not an official correction. It can move a finding to `partially_explained`, but only publisher evidence can establish `formally_corrected`.

**Acceptance**

- Report shows a timeline: observed version → response → current publisher status.
- A stale mismatch is not double-counted after a verified correction.
- A response lacking publisher confirmation cannot erase the original visible inconsistency.

### Task 7: Promote measurement precision into a real time-series quantization detector

**Files**

- Create: `integrity_agent/detectors/numeric/quantization_grid.py`
- Modify in place: `knowledge_base/detector_rules/measurement_precision_anomaly.yml` (promote `draft_spec_only` to an active, registered detector only after tests pass)
- Modify: `integrity_agent/detectors/registry.py`
- Modify: `integrity_agent/workflows/table_numeric_review.py`
- Test: `tests/test_quantization_grid_detector.py`
- Fixture: `examples/toy_table_package/toy_quantized_timeseries.csv`
- Fixture: `examples/toy_table_package/toy_declared_resolution_timeseries.csv`
- Docs: `docs/QUANTIZATION_GRID_REVIEW.md`

**Metrics to emit, not hide**

- total and unique counts;
- unique ratio;
- modal-value frequency;
- run-length distribution;
- minimum observed step;
- best-fit lattice step and residual;
- overlap of quantization grids across related curves;
- declared instrument/export resolution if available.

**Detector boundary**

- No fixed threshold copied from the Nature Energy post.
- Calibrate thresholds using synthetic continuous, rounded, quantized and normalized series.
- If instrument/export resolution is unknown, cap at low/medium and request raw export.
- Repetition consistent with declared resolution should be downgraded or suppressed.

**Acceptance**

1. Detect a synthetic lattice-quantized series.
2. Do not flag ordinary 3-decimal instrument output when declared resolution explains it.
3. Do not treat shared normalization grids as proof of duplicated measurements.
4. Small samples are downgraded.
5. Finding includes a machine-readable reproducibility summary and safe language.

### Task 7A: Harden existing terminal-digit and fixed-delta detectors

**Files**

- Modify: `integrity_agent/detectors/numeric/terminal_digit.py`
- Modify: `integrity_agent/detectors/numeric/fixed_delta.py`
- Modify: `knowledge_base/detector_rules/numeric_terminal_digit_anomaly.yml`
- Modify: `knowledge_base/detector_rules/numeric_fixed_delta_between_columns.yml`
- Modify: `integrity_agent/workflows/table_numeric_review.py`
- Test: `tests/test_numeric_detector_context_controls.py`

**Confirmed design debt**

- Small-sample risk behavior currently contains toy-file-name exceptions.
- Fixed-delta scans numeric column pairs without proving that they represent independent measurements.
- The YAML detection idea says differences/ratios, while the runtime implementation computes differences only.
- `ColumnProfile.precision_hint` already exists and should be consumed rather than reimplemented.

**Acceptance**

1. IDs, row indices, declared formula columns, Kelvin/°C conversions, normalizations and disclosed derived columns do not become integrity findings.
2. Small samples are always low risk or suppressed; fixture file names never alter scientific risk.
3. Fixed-delta reports only when column semantics support nominally independent measurements; otherwise it emits a context question.
4. Either implement a conservative ratio check with dedicated tests or narrow the YAML to the actual delta-only runtime contract.
5. Correlated terminal-digit/quantization/fixed-delta signals retain separate evidence but do not automatically imply a higher misconduct probability.

### Task 8: Reuse, do not rewrite, the PCE consistency detector

**Files**

- Modify only if tests expose a real defect: `integrity_agent/domains/photovoltaics/pce_consistency.py`
- Test: `tests/test_pv_pce_consistency_multiscan_regression.py`
- Modify: `docs/PV_FALSE_POSITIVE_GUIDE.md`

**Steps**

1. Add a synthetic 8-row, forward/reverse, control/target regression matrix.
2. Confirm row-level source locations and reported/recomputed values.
3. Test 100 mW cm⁻² and non-1-sun cases.
4. Test rounded printed values vs hidden-precision tolerance.
5. Keep the existing default tolerance unless a benchmark, not a single paper, justifies change.

**Acceptance**

- Existing behavior still catches clearly inconsistent rows.
- Non-standard illumination and stabilized-vs-scan PCE are explicit alternatives.
- No duplicate detector is added.

---

## P2 — Domain-specific reconciliation after P0/P1 is stable

### Task 9: Add TRPL/TPV fit and unit reconciliation

**Files**

- Create: `integrity_agent/domains/photovoltaics/decay_fit_consistency.py`
- Create: `knowledge_base/detector_rules/pv_decay_fit_consistency.yml`
- Modify: `integrity_agent/workflows/pv_domain_review.py`
- Test: `tests/test_pv_decay_fit_consistency.py`
- Docs: `docs/PV_DECAY_FIT_CHECKS.md`

**Requirements**

- Normalize ns/μs/ms.
- Support both commonly used average-lifetime conventions:
  - amplitude-weighted `ΣAiτi / ΣAi`;
  - intensity-weighted `ΣAiτi² / ΣAiτi`.
- Require the declared formula before calling a mismatch; otherwise report formula ambiguity.
- Compare figure annotation, fit table and source-fit parameters for the same sample/version.

**Acceptance**

- Correct unit conversion passes.
- Wrong table/figure value triggers a candidate signal.
- Two valid average-lifetime conventions do not create a false positive.
- Revised SI can resolve the original-version mismatch while preserving history.

### Task 10: Add source-data-to-plot point reconciliation

**Files**

- Create: `integrity_agent/core/curves/schema.py`
- Create: `integrity_agent/workflows/curve_reconciliation.py`
- Create: `knowledge_base/detector_rules/curve_point_coverage.yml`
- Test: `tests/test_curve_point_coverage.py`
- Docs: `docs/CURVE_SOURCE_RECONCILIATION.md`

**Boundary**

- Operate on provided source CSV/XLSX and plot-data tables, not image digitization in v1.
- Distinguish axis clipping, downsampling, smoothing, NaNs and disclosed filtering from unexplained omitted intervals.

**Acceptance**

- A disclosed downsampled curve does not trigger.
- An unexplained missing contiguous voltage/time interval creates a review question.
- No claim of “deleted data” is emitted without source mapping and plotting context.

### Task 11: Add process-lineage questions for DLS/filtration without an impossibility verdict

**Files**

- Create: `integrity_agent/domains/materials_characterization/process_lineage.py`
- Create: `knowledge_base/detector_rules/materials_sample_lineage.yml`
- Test: `tests/test_materials_process_lineage.py`
- Docs: `docs/MATERIALS_PROCESS_LINEAGE.md`

**Logic**

Model sample stages: preparation → sonication/vortex → filtration → storage → DLS → deposition. Compare pore size and reported hydrodynamic diameter only when measurement stage and distribution basis are known.

**Acceptance**

- `DLS after filtration` + particle size much larger than nominal pore creates a low-risk verification question.
- Unknown measurement stage yields missing-context only.
- Alternatives include filter nominal-vs-effective pore, deformable/soft particles, intensity-weighted rare aggregates and post-filtration aggregation.
- The detector never emits “physically impossible” or misconduct language.

### Task 12: Defer automatic PDF/OCR claim extraction until deterministic benchmarks pass

**Future files only after approval**

- Possible: `integrity_agent/workflows/document_claim_extract_draft.py`
- Possible tests: `tests/test_document_claim_extract_draft.py`

Any extraction must output `human_confirmed: false`; it cannot create findings until a reviewer confirms source location, device variant, unit and version. This phase is intentionally deferred because premature LLM/OCR automation would amplify exactly the context errors exposed by the EES and AFM cases.

---

## Integration and release gate

### Task 13: Unified runner, dashboard and regression gate

**Files**

- Modify: `integrity_agent/workflows/review_package.py`
- Modify: `integrity_agent/core/packages/package_schema.py`
- Modify: `integrity_agent/workflows/report_reader_review.py`
- Modify: `integrity_agent/core/reporting/html_dashboard.py`
- Modify: `integrity_agent/core/risk_model/risk_calculator.py`
- Modify: `docs/REVIEW_PACKAGE_RUNNER.md`
- Modify: `docs/CLI_REFERENCE.md`
- Modify: `docs/ARCHITECTURE.md`
- Test: `tests/test_review_package_document_claims.py`
- Test: `tests/test_review_package_version_status.py`
- Test: `tests/test_review_package_scope_firewall.py`
- Test: `tests/test_review_package_ledger_gate.py`
- Test: `tests/test_risk_calculator_correlation_groups.py`

**Required report fields**

- source fact;
- detector/recomputation result;
- mechanism interpretation;
- transferability/verification request;
- evidence tier;
- source version and resolution status;
- counter-evidence;
- alternative benign explanations;
- do-not-overclaim warning.

**Commands**

```bash
# Run from the repository root.
python -m pytest -q tests/test_document_claim_schema.py \
  tests/test_cross_document_claim_consistency.py \
  tests/test_version_reconciliation.py \
  tests/test_quantization_grid_detector.py \
  tests/test_pv_decay_fit_consistency.py
python -m pytest -q
python -m integrity_agent review-package examples/toy_review_package \
  -o outputs/perovskite_cross_document_smoke
python -m integrity_agent validate-ledger \
  outputs/perovskite_cross_document_smoke/unified_evidence_index.jsonl
```

**Release acceptance**

1. Baseline 241 tests plus all new tests pass.
2. Existing packages without `documents/` produce backward-compatible output.
3. Every new finding validates against the unified ledger schema.
4. No non-official finding exceeds `medium` risk.
5. A version-resolved discrepancy is preserved historically but not counted as an open contradiction.
6. Engineering-plausibility items contribute zero to integrity MRPI.
7. No social auth material, full post dump, article PDF/SI or screenshots enter git.
8. Offline smoke test performs no network access.
9. The runner validates the final unified ledger internally; an invalid record prevents unconditional `success`.
10. Findings in the same `(source, table, method_family/correlation_group)` remain traceable but contribute only one group-level MRPI weight.

## Recommended execution order

1. **Correctness first**: B1–B4 as separate, regression-driven fixes. No new detectors in these PRs.
2. **Provenance and safety**: Tasks 1–3 after B1–B4 are green.
3. **Cross-document core**: Tasks 4–6.
4. **Numeric upgrade**: Tasks 7 and 7A; consume existing `ColumnProfile.precision_hint` rather than building a second profiler, and harden the current terminal-digit/fixed-delta semantics.
5. **Reuse checkpoint**: Task 8; verify current PCE module rather than rewriting it.
6. **P2 only after benchmark review**: Tasks 9–11.
7. **Automatic extraction remains deferred**: Task 12.
8. **Release gate**: Task 13 and full offline smoke.

## Direct priority judgment

- **Immediate highest ROI**: B1 package-path/status correctness and B2 PV context mapping. Without them, existing detectors silently miss real inputs or generate false findings.
- **Next**: B3 materials tokenization and B4 enforceable case/safety contracts.
- **First new capability**: cross-document claim schema + version reconciliation.
- **Second new capability**: time-series quantization with instrument-resolution alternatives.
- **Third new capability**: TRPL/TPV deterministic fit/unit reconciliation.
- **Low ROI / reject from core**: Xiaohongshu crawler integration, vendor price monitoring, motive inference and general “industrial value” scoring.
