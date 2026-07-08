# PV Evidence Ruleset v1 Taxonomy Implementation Summary

This document summarizes the design, implementation, and verification of the Photovoltaics (PV) Evidence Ruleset v1 taxonomy in the Research Integrity Evidence Review Agent repository.

## 1. Scope & Ruleset Design

The new taxonomy defines **26 rules** across 5 categories:

### Group 1: J-V reporting
- `pv_jv_scan_direction_completeness`: Check if scan direction is specified.
- `pv_jv_hysteresis_reporting`: Check if both forward and reverse scans are provided.
- `pv_jv_mask_area_completeness`: Check if mask area is documented.
- `pv_jv_light_intensity_completeness`: Check if light intensity is reported.
- `pv_stabilized_power_output_reporting`: Check if stabilized power output or steady-state PCE is missing.
- `pv_mpp_tracking_completeness`: Check if MPP tracking parameters are specified.

### Group 2: EQE/J-V
- `pv_eqe_integrated_jsc_consistency`: Mismatch between integrated EQE current and simulator Jsc.
- `pv_eqe_spectrum_range_completeness`: Check if EQE spectrum wavelength range is reported.
- `pv_am15g_reference_completeness`: Check if the reference standard is specified.
- `pv_eqe_reflection_correction`: Check if reflection or parasitic absorption correction is reported.

### Group 3: Stability
- `pv_isos_condition_reporting`: Check if standard ISOS protocols are designated.
- `pv_stability_uv_dose`: Check if UV illumination intensity or dose is reported.
- `pv_stability_humidity`: Check if relative humidity (RH) is reported.
- `pv_stability_temperature`: Check if temperature is reported.
- `pv_stability_encapsulation`: Check if encapsulation status is reported.
- `pv_stability_tracking_mode`: Check for distinction between continuous MPP tracking and dark shelf storage.

### Group 4: Tandem
- `pv_tandem_bandgap_completeness`: Check if top and bottom subcell bandgaps are reported.
- `pv_tandem_current_matching`: Check for current mismatch between top/bottom subcells in 2T tandems.
- `pv_tandem_spectral_mismatch`: Check if spectral mismatch factors are reported.
- `pv_tandem_aperture_area`: Check if aperture area is documented.
- `pv_tandem_shadow_mask`: Check if shadow mask presence is specified.
- `pv_tandem_connection_consistency`: Check if terminal configuration (2T/4T) is specified and physically consistent.

### Group 5: Materials characterization
- `pv_materials_composition`: Check if detailed chemical stoichiometry is specified.
- `pv_materials_sam_interface`: Check if SAM or interface passivation treatment parameters are reported.
- `pv_materials_sputter_damage`: Check if sputter/ALD damage mitigation details are reported.
- `pv_materials_metadata`: Check if experimental metadata for XRD/SEM/PL/UPS/XPS is reported.

---

## 2. Safety and Verdict Boundaries Compliance

- **No verdict phrases**: In compliance with [AGENTS.md](../AGENTS.md) and [safety.py](../integrity_agent/core/safety.py), all taxonomy items use non-accusatory terms. Words like "fake", "fraud", or "misconduct" are strictly forbidden. The safe report language uses phrasing like *"candidate completeness gap"* or *"needs manual verification"*.
- **Caveat on High Risk Ceiling**: For high-risk ceiling rules (`pv_eqe_integrated_jsc_consistency`), a clear caveat is included stating that a high-risk rating for physical inconsistencies is subject to missing raw/source-data verification caveats.
- **Benign Alternatives**: Every single rule includes a predefined list of alternative benign explanations and false positive risks.

---

## 3. CLI export command: `pv-ruleset-export`

The new command exports the taxonomy to JSON and Markdown format:
```bash
python -m integrity_agent pv-ruleset-export
```
By default, this writes to:
1. `outputs/pv_ruleset_v1/pv_evidence_ruleset_v1.json`
2. `outputs/pv_ruleset_v1/pv_evidence_ruleset_v1.md`

---

## 4. Test Verification Results

All tests pass cleanly:
- `tests/test_pv_evidence_ruleset_v1.py` validates structure, safety boundaries, and export.
- `tests/test_p2_release_readiness.py` verifies CLI command integration and documentation existence/safety disclaimers.
