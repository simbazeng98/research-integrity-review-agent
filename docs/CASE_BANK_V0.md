# Case Bank V0

This first batch contains 12 case cards selected for rule distillation, not for
accusation. Each card keeps only structured summaries, source links, evidence
patterns, detector candidates, false-positive risks, manual-verification needs,
and safe report language.

## Selection Groups

- P0 official or strongly structured sources: ORI findings, public numerical
  anomaly reporting with institutional follow-up, and publisher-scale paper-mill
  retractions.
- P1 high-value reader-review examples: AI-altered clinical image retraction,
  high-stakes materials claims, landmark image-integrity retraction, institutional
  image/data cluster review, and tortured-phrase screening.
- P2 benchmark and detector-risk sources: withdrawn-preprint taxonomy, western
  blot AI-detector limitations, and synthetic-manipulation localization.

## Guardrails

- A case card is a rule-distillation seed, not a verdict template.
- `public_status` must stay explicit because withdrawal, correction, retraction,
  settlement, public allegation, and official misconduct finding are different.
- Dataset and benchmark cards must not be used as misconduct labels.
- Every detector candidate needs false-positive risks and manual-verification
  requirements before implementation.

## Files

- `case_bank_v0_001_ori_ke_chen_yeh.yml`
- `case_bank_v0_002_ori_daniel_andrade.yml`
- `case_bank_v0_003_geng_tongji_public_reporting.yml`
- `case_bank_v0_004_hindawi_wiley_paper_mill.yml`
- `case_bank_v0_005_nejm_ai_clinical_image.yml`
- `case_bank_v0_006_ranga_dias_superconductivity.yml`
- `case_bank_v0_007_abeta56_alzheimer_retraction.yml`
- `case_bank_v0_008_dana_farber_image_cluster.yml`
- `case_bank_v0_009_problematic_paper_screener.yml`
- `case_bank_v0_010_withdrarxiv.yml`
- `case_bank_v0_011_ai_detector_western_blot_risk.yml`
- `case_bank_v0_012_western_blot_synthetic_localization.yml`
