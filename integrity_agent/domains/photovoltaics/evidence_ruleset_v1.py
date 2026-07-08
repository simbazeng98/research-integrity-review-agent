from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class TaxonomyItem:
    rule_id: str
    category: str
    required_evidence: list[str]
    missing_evidence_signal: str
    manual_verification_questions: list[str]
    benign_alternatives: list[str]
    false_positive_risks: list[str]
    risk_ceiling: str  # must be 'low', 'medium', or 'high'
    safe_report_language: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

TAXONOMY_RULESET: list[TaxonomyItem] = [
    # Group 1: J-V reporting
    TaxonomyItem(
        rule_id="pv_jv_scan_direction_completeness",
        category="J-V reporting",
        required_evidence=["scan_direction"],
        missing_evidence_signal="Scan direction (forward or reverse) is not specified for J-V characterization.",
        manual_verification_questions=[
            "Verify whether the J-V scan direction is reported in the text or figures of the manuscript.",
            "Consult the original instrument configuration files to determine the sweep direction."
        ],
        benign_alternatives=[
            "The devices have negligible hysteresis, making the sweep direction irrelevant for power conversion efficiency.",
            "The sweep direction is detailed in the experimental/methods section rather than the data table."
        ],
        false_positive_risks=[
            "A single-direction sweep was used but described as the standard lab setup in the manuscript text."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate J-V scan direction completeness gap: the scan direction (forward/reverse) is not explicitly documented in the dataset. Manual verification is needed to confirm the measurement parameters."
    ),
    TaxonomyItem(
        rule_id="pv_jv_hysteresis_reporting",
        category="J-V reporting",
        required_evidence=["forward_scan_pce_percent", "reverse_scan_pce_percent"],
        missing_evidence_signal="Hysteresis evaluation is missing (either forward or reverse scan data is not provided, or hysteresis factor is not calculated).",
        manual_verification_questions=[
            "Are both forward and reverse J-V scans provided for the champion device?",
            "Does the discrepancy between forward and reverse scan PCEs exceed standard tolerances?"
        ],
        benign_alternatives=[
            "The device belongs to a technology class (e.g., organic or silicon photovoltaics) that does not exhibit substantial hysteresis.",
            "The authors reported stabilized power output at MPP instead of dual-direction sweeps."
        ],
        false_positive_risks=[
            "The device has zero hysteresis, so only one scan direction was deemed necessary to report by the authors."
        ],
        risk_ceiling="medium",
        safe_report_language="Candidate J-V hysteresis reporting signal: both scan directions are required to evaluate hysteresis, but only one is present or hysteresis calculation is omitted. Manual review of raw forward/reverse sweeps is suggested."
    ),
    TaxonomyItem(
        rule_id="pv_jv_mask_area_completeness",
        category="J-V reporting",
        required_evidence=["mask_area_cm2"],
        missing_evidence_signal="Aperture mask area is not specified, leaving the exact illuminated device area ambiguous.",
        manual_verification_questions=[
            "Is the aperture mask area reported in the text or supplementary information?",
            "Was a physical metal mask used during J-V testing, and what was its area?"
        ],
        benign_alternatives=[
            "The active area is defined solely by the electrode overlap and no aperture mask was used.",
            "Mask dimensions are defined in a general experimental section rather than in the table."
        ],
        false_positive_risks=[
            "The table column headers use custom labels for mask area that were not parsed."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate device mask area completeness gap: mask area is not specified in the parsed dataset. Manual verification is recommended to ensure consistency in area definitions."
    ),
    TaxonomyItem(
        rule_id="pv_jv_light_intensity_completeness",
        category="J-V reporting",
        required_evidence=["light_intensity_mw_cm2"],
        missing_evidence_signal="Light intensity (e.g., 100 mW/cm^2 or 1 sun equivalent) is not reported.",
        manual_verification_questions=[
            "Verify the calibrated light simulator intensity (in mW/cm^2 or Suns) in the experimental methods.",
            "Check if measurements were performed under dark or partial illumination."
        ],
        benign_alternatives=[
            "All measurements were performed under standard 1-sun illumination (100 mW/cm^2), which was assumed implicitly by the researchers."
        ],
        false_positive_risks=[
            "Irradiance values are documented in a parent calibration record rather than individual row metadata."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate light intensity completeness gap: light intensity is not explicitly reported in the parsed columns. Manual review is requested to confirm standard AM1.5G testing conditions."
    ),
    TaxonomyItem(
        rule_id="pv_stabilized_power_output_reporting",
        category="J-V reporting",
        required_evidence=["stabilized_power_output_percent"],
        missing_evidence_signal="Stabilized power output (SPO) or steady-state PCE under illumination is not reported.",
        manual_verification_questions=[
            "Is a stabilized power output tracking curve included in the figures or SI?",
            "For how many seconds or minutes was the device tracked to establish steady-state PCE?"
        ],
        benign_alternatives=[
            "The device undergoes rapid transient degradation under continuous illumination, making long-term SPO tracking unfeasible.",
            "SPO is only reported for the champion cell in a figure, not in the main data tables."
        ],
        false_positive_risks=[
            "The dataset focuses on initial screening of a large batch where SPO tracking is not standard procedure."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate stabilized power output reporting gap: stabilized power output or steady-state PCE is missing from the dataset. Needs manual verification of device stability under illumination."
    ),
    TaxonomyItem(
        rule_id="pv_mpp_tracking_completeness",
        category="J-V reporting",
        required_evidence=["mpp_tracking"],
        missing_evidence_signal="Maximum Power Point (MPP) tracking configuration (algorithm, voltage step, or duration) is not reported.",
        manual_verification_questions=[
            "What MPP tracking algorithm (e.g., perturb and observe) was utilized?",
            "What was the total duration of the MPP tracking experiment?"
        ],
        benign_alternatives=[
            "The stability was measured at a fixed bias voltage (near Vmp) rather than active tracking.",
            "The MPP details are reported in the methods text or figure caption rather than tabular data."
        ],
        false_positive_risks=[
            "Standard tracking software defaults were used without explicit notation."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate MPP tracking completeness gap: MPP tracking parameters are not specified. Manual verification of the tracking protocol is suggested."
    ),

    # Group 2: EQE/J-V
    TaxonomyItem(
        rule_id="pv_eqe_integrated_jsc_consistency",
        category="EQE/J-V",
        required_evidence=["eqe_jsc_ma_cm2", "jsc_ma_cm2"],
        missing_evidence_signal="High mismatch between integrated EQE Jsc and J-V simulator Jsc (relative deviation > 10%).",
        manual_verification_questions=[
            "Compare the integrated EQE Jsc against the J-V Jsc for the exact same device.",
            "Verify the spectrum integration calculations and standard AM1.5G reference table used."
        ],
        benign_alternatives=[
            "Spectral mismatch correction was not applied to the simulator calibration.",
            "The cell degraded significantly between the J-V measurement and the EQE measurement.",
            "Differences in aperture mask area or alignment between J-V and EQE setups."
        ],
        false_positive_risks=[
            "The EQE Jsc and J-V Jsc are reported for different devices (e.g., champion vs average)."
        ],
        risk_ceiling="high",
        safe_report_language="Candidate EQE and J-V Jsc inconsistency signal: the relative deviation between integrated EQE Jsc and simulator-derived Jsc exceeds standard tolerance. Warning: A high-risk rating for physical inconsistencies is subject to missing raw/source-data verification caveats; manual review of original spectral files and simulator calibration is required."
    ),
    TaxonomyItem(
        rule_id="pv_eqe_spectrum_range_completeness",
        category="EQE/J-V",
        required_evidence=["eqe_spectrum_range"],
        missing_evidence_signal="EQE wavelength range is too narrow or not reported, missing essential spectral response.",
        manual_verification_questions=[
            "Does the reported EQE spectrum cover the full absorption range of the active material?",
            "Verify if the EQE wavelength step and bounds are documented."
        ],
        benign_alternatives=[
            "The monochromator source had hardware limits at UV or near-IR wavelengths.",
            "The active material bandgap lies well within the measured range, making wider scans unnecessary."
        ],
        false_positive_risks=[
            "The data is presented as a chart where the range is visible but not in the metadata table."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate EQE spectrum range completeness gap: the wavelength range of the EQE spectrum is not specified. Manual verification of the measured spectral boundaries is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_am15g_reference_completeness",
        category="EQE/J-V",
        required_evidence=["am15g_reference_standard"],
        missing_evidence_signal="Standard AM1.5G reference spectrum version (e.g. ASTM G173-03 or IEC 60904-3) is not reported.",
        manual_verification_questions=[
            "Which ASTM or IEC standard AM1.5G spectral irradiance data was used for integration?",
            "Verify the spectral irradiance values used in the EQE integration calculations."
        ],
        benign_alternatives=[
            "The standard software defaults (usually ASTM G173-03) were used without explicitly citing the version in the table."
        ],
        false_positive_risks=[
            "The standard is cited in the main text bibliography rather than the data table."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate AM1.5G reference completeness gap: reference standard for solar simulator or EQE integration is not specified. Manual verification is needed."
    ),
    TaxonomyItem(
        rule_id="pv_eqe_reflection_correction",
        category="EQE/J-V",
        required_evidence=["reflection_correction_applied"],
        missing_evidence_signal="Reporting of reflection or parasitic absorption correction for EQE/IQE is missing.",
        manual_verification_questions=[
            "Was reflectance measured and used to calculate Internal Quantum Efficiency (IQE)?",
            "Was parasitic absorption in the substrate/TCO corrected for in the reported efficiency?"
        ],
        benign_alternatives=[
            "No reflection correction was applied, meaning the reported EQE represents external quantum efficiency without adjustments.",
            "Reflectance was negligible or not measured."
        ],
        false_positive_risks=[
            "IQE is not claimed in the paper, so reflection correction is not applicable."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate EQE reflection correction completeness gap: reflection/parasitic absorption correction is not specified. Manual verification of correction status is suggested."
    ),

    # Group 3: Stability
    TaxonomyItem(
        rule_id="pv_isos_condition_reporting",
        category="Stability",
        required_evidence=["isos_protocol"],
        missing_evidence_signal="Standard ISOS stability testing protocol designation (e.g. ISOS-D-1, ISOS-L-1) is not reported.",
        manual_verification_questions=[
            "Which specific ISOS protocol (e.g. ISOS-L-1, ISOS-D-2) was followed?",
            "Do the actual stress conditions match the designated ISOS protocol specifications?"
        ],
        benign_alternatives=[
            "The stability test was customized and did not follow standardized ISOS protocols.",
            "The protocol name is mentioned in the manuscript text rather than the summary table."
        ],
        false_positive_risks=[
            "The aging experiment was performed before the consensus ISOS protocols were widely adopted."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate ISOS condition reporting gap: the standard ISOS protocol designation is missing. Manual verification of the aging protocol is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_stability_uv_dose",
        category="Stability",
        required_evidence=["uv_exposure_dose"],
        missing_evidence_signal="UV illumination intensity or cumulative dose is not reported for UV-stability tests.",
        manual_verification_questions=[
            "Was UV light included in the illumination source during stability testing?",
            "What was the spectral distribution and intensity of the UV component?"
        ],
        benign_alternatives=[
            "The solar simulator had a UV-blocking filter, or the test did not focus on UV stability.",
            "UV exposure is assumed to be standard AM1.5G UV component without separate measurement."
        ],
        false_positive_risks=[
            "The aging experiment was conducted in the dark or under visible LED illumination only, making UV dose irrelevant."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate UV dose stability reporting gap: UV exposure parameters are not reported. Manual check of light source UV content is suggested."
    ),
    TaxonomyItem(
        rule_id="pv_stability_humidity",
        category="Stability",
        required_evidence=["humidity_percent"],
        missing_evidence_signal="Relative humidity (RH) is not reported for stability tests.",
        manual_verification_questions=[
            "What was the relative humidity during stability testing?",
            "Was the device aged in a controlled humidity chamber or ambient air?"
        ],
        benign_alternatives=[
            "The devices were stored/aged in a nitrogen glovebox where humidity is continuously monitored and kept below 1 ppm.",
            "Humidity is described in the experimental section rather than the dataset."
        ],
        false_positive_risks=[
            "The table summarizes dry-storage tests where humidity control is not relevant."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate stability humidity completeness gap: relative humidity is not reported. Manual review of the environmental conditions is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_stability_temperature",
        category="Stability",
        required_evidence=["temperature_c"],
        missing_evidence_signal="Temperature is not reported for stability tests.",
        manual_verification_questions=[
            "What was the device or ambient temperature during aging?",
            "Was a cooling system used to maintain constant temperature under light soaking?"
        ],
        benign_alternatives=[
            "Measurements were performed at room temperature, which was assumed implicitly.",
            "The temperature is detailed in the text/methods section."
        ],
        false_positive_risks=[
            "The table lists multiple stability conditions but omits the temperature column due to space limits."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate stability temperature completeness gap: temperature is not reported. Manual review of temperature conditions is suggested."
    ),
    TaxonomyItem(
        rule_id="pv_stability_encapsulation",
        category="Stability",
        required_evidence=["encapsulation"],
        missing_evidence_signal="Encapsulation status or materials are not reported for stability tests.",
        manual_verification_questions=[
            "Were the devices encapsulated during stability testing?",
            "What encapsulation materials (e.g. epoxy, glass cover slip) were used?"
        ],
        benign_alternatives=[
            "The devices were tested bare (unencapsulated) to evaluate intrinsic material stability.",
            "Encapsulation procedure is described in the methods section."
        ],
        false_positive_risks=[
            "All devices were encapsulated using a standard lab recipe, which is cited in the paper."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate encapsulation reporting gap: encapsulation status is not reported. Manual verification of encapsulation conditions is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_stability_tracking_mode",
        category="Stability",
        required_evidence=["stability_tracking_mode"],
        missing_evidence_signal="Distinction between continuous MPP tracking and shelf storage (with intermittent testing) is not reported.",
        manual_verification_questions=[
            "Was the device under continuous load/bias during aging, or stored on a shelf and tested periodically?",
            "For shelf storage, what were the storage environment conditions?"
        ],
        benign_alternatives=[
            "The stability test was a simple shelf-lifetime study in the dark.",
            "The mode is described in the text of the manuscript rather than the table."
        ],
        false_positive_risks=[
            "The test uses standard defaults that are implied by the listed ISOS protocol."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate stability tracking mode reporting gap: continuous tracking vs shelf storage distinction is not specified. Manual verification is recommended."
    ),

    # Group 4: Tandem
    TaxonomyItem(
        rule_id="pv_tandem_bandgap_completeness",
        category="Tandem",
        required_evidence=["bandgap_ev"],
        missing_evidence_signal="Bandgaps of top and bottom subcells are not both reported for a tandem device.",
        manual_verification_questions=[
            "What are the optical or electronic bandgaps of the top and bottom absorber layers?",
            "Are the bandgap values consistent with the reported EQE spectra?"
        ],
        benign_alternatives=[
            "The paper focuses on a single subcell and uses a standard commercial bottom cell without measuring its bandgap.",
            "The bandgaps are reported in a separate materials section rather than the device performance table."
        ],
        false_positive_risks=[
            "The subcell bandgaps are documented in different tables."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate tandem bandgap completeness gap: bandgaps of both top and bottom subcells are not reported in the table. Manual verification is needed."
    ),
    TaxonomyItem(
        rule_id="pv_tandem_current_matching",
        category="Tandem",
        required_evidence=["eqe_jsc_ma_cm2"],
        missing_evidence_signal="Significant mismatch in integrated current density between top and bottom subcells (exceeding 2 mA/cm^2) in a series-connected 2T tandem.",
        manual_verification_questions=[
            "What are the integrated Jsc values for the top and bottom subcells?",
            "Is the tandem device current-limited by the top or bottom cell?"
        ],
        benign_alternatives=[
            "The tandem device is in a 4T (four-terminal) configuration, where current matching is not required.",
            "Measurements were performed under non-standard spectra where matching is altered."
        ],
        false_positive_risks=[
            "The table reports values for a 4T configuration but does not explicitly label the terminal configuration."
        ],
        risk_ceiling="medium",
        safe_report_language="Candidate tandem current matching signal: current mismatch between top and bottom subcells exceeds standard limits for 2T tandems. Manual review of subcell configuration and EQE curves is suggested."
    ),
    TaxonomyItem(
        rule_id="pv_tandem_spectral_mismatch",
        category="Tandem",
        required_evidence=["spectral_mismatch_factor"],
        missing_evidence_signal="Spectral mismatch factor (SMF) calculations or calibration adjustments are not reported for tandem measurements.",
        manual_verification_questions=[
            "Was spectral mismatch correction applied separately for top and bottom subcell calibrations?",
            "What reference cell was used to calibrate the dual-source simulator?"
        ],
        benign_alternatives=[
            "Dual-source simulator spectral mismatch was calibrated to be negligible, or standard AM1.5G was assumed.",
            "Details are in the supplementary information rather than the main table."
        ],
        false_positive_risks=[
            "The paper reports uncorrected performance metrics which are explicitly labeled as such in the text."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate tandem spectral mismatch completeness gap: spectral mismatch factor is not specified. Manual verification of calibration procedures is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_tandem_aperture_area",
        category="Tandem",
        required_evidence=["aperture_area_cm2"],
        missing_evidence_signal="Aperture area is not reported for tandem devices, which is critical due to current sharing and shading effects.",
        manual_verification_questions=[
            "Is the aperture area defined by a mask reported?",
            "How does the aperture area compare to the active cell area?"
        ],
        benign_alternatives=[
            "The active area is defined by the physical overlap of electrodes and no aperture mask was used.",
            "Area parameters are described in the methods text."
        ],
        false_positive_risks=[
            "The table headers use non-standard terminology for aperture area."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate tandem aperture area completeness gap: aperture area is not reported. Manual verification of the cell layout and area definition is suggested."
    ),
    TaxonomyItem(
        rule_id="pv_tandem_shadow_mask",
        category="Tandem",
        required_evidence=["shadow_mask_present"],
        missing_evidence_signal="Use of a shadow mask during tandem characterization is not reported.",
        manual_verification_questions=[
            "Was a shadow mask placed over the tandem cell to prevent overestimation of current?",
            "What were the dimensions of the shadow mask?"
        ],
        benign_alternatives=[
            "No shadow mask was used, and current was measured over the entire substrate area.",
            "Shadow mask usage is reported in the methods text."
        ],
        false_positive_risks=[
            "The dataset includes cells that are too small or structured such that shadow masks are not standard."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate tandem shadow mask reporting gap: shadow mask presence is not specified. Manual verification of testing geometry is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_tandem_connection_consistency",
        category="Tandem",
        required_evidence=["connection_type"],
        missing_evidence_signal="The tandem terminal configuration (2T vs 4T) is not specified, or performance parameters are physically inconsistent with the claimed connection type (e.g. 2T device with non-matching currents or independent subcell Voc additions).",
        manual_verification_questions=[
            "Is the tandem device connected in a 2-terminal (2T) or 4-terminal (4T) configuration?",
            "Verify whether the reported tandem Voc matches the sum of subcell Vocs in a 2T configuration."
        ],
        benign_alternatives=[
            "The tandem device was tested both in 2T and 4T configurations, and headers are aggregated.",
            "The connection type is described in the manuscript text."
        ],
        false_positive_risks=[
            "The dataset represents a novel multi-terminal configuration not categorized as 2T or 4T."
        ],
        risk_ceiling="medium",
        safe_report_language="Candidate tandem connection type consistency signal: terminal configuration is unspecified or displays physical inconsistencies with performance parameters. Manual review of cell schematics is recommended."
    ),

    # Group 5: Materials characterization
    TaxonomyItem(
        rule_id="pv_materials_composition",
        category="Materials characterization",
        required_evidence=["chemical_composition"],
        missing_evidence_signal="Detailed chemical stoichiometry or composition (e.g., specific halide ratios in perovskites) is not reported.",
        manual_verification_questions=[
            "What is the nominal stoichiometry of the absorber layer?",
            "Was the elemental composition verified experimentally (e.g., by XPS or EDX)?"
        ],
        benign_alternatives=[
            "The composition is a standard material (e.g., MAPbI3) and stoichiometry is assumed.",
            "Detailed stoichiometry is given in the text rather than the summary table."
        ],
        false_positive_risks=[
            "The study focuses on device engineering rather than material composition variations."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate materials composition completeness gap: detailed chemical composition is not reported in the table. Manual verification is suggested."
    ),
    TaxonomyItem(
        rule_id="pv_materials_sam_interface",
        category="Materials characterization",
        required_evidence=["interface_treatment"],
        missing_evidence_signal="Self-Assembled Monolayer (SAM) or interface passivation treatment parameters are not reported.",
        manual_verification_questions=[
            "What interface passivation or SAM material was applied?",
            "What were the concentration, solvent, and deposition conditions for the interface treatment?"
        ],
        benign_alternatives=[
            "No interface treatment or SAM was used in the control or experimental devices.",
            "Treatment details are described in the methods text."
        ],
        false_positive_risks=[
            "The database has parsed a simplified cell structure where passivation details are omitted."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate interface treatment completeness gap: SAM or interface treatment details are missing. Manual check of the experimental methods is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_materials_sputter_damage",
        category="Materials characterization",
        required_evidence=["deposition_damage_mitigation"],
        missing_evidence_signal="Deposition parameters or buffer layer details mitigating Atomic Layer Deposition (ALD) or Transparent Conducting Oxide (TCO) sputter damage are not reported.",
        manual_verification_questions=[
            "Was a buffer layer (e.g., ALD SnO2 or sputtered ITO) deposited, and how was damage to the underlying absorber mitigated?",
            "What were the RF sputter power or ALD temperature during deposition?"
        ],
        benign_alternatives=[
            "No sputtered layers or ALD steps were used in the device architecture.",
            "Damage mitigation is discussed qualitatively in the text."
        ],
        false_positive_risks=[
            "Sputtering was performed under standard lab conditions described in a previous reference."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate sputter/ALD damage mitigation completeness gap: buffer layer or deposition parameters are not specified. Manual verification is recommended."
    ),
    TaxonomyItem(
        rule_id="pv_materials_metadata",
        category="Materials characterization",
        required_evidence=["materials_characterization_metadata"],
        missing_evidence_signal="Core experimental metadata for XRD, SEM, PL, UPS, or XPS measurements is not reported.",
        manual_verification_questions=[
            "What instrument models, excitation wavelengths, or scanning parameters were used for materials characterization?",
            "Are calibration reference files or background subtraction steps documented?"
        ],
        benign_alternatives=[
            "Standard university user facility instrument setups were used without special configuration.",
            "Characterization details are in the SI text."
        ],
        false_positive_risks=[
            "The table only summarizes device performance metrics, and characterization raw data is kept in separate facility logs."
        ],
        risk_ceiling="low",
        safe_report_language="Candidate materials characterization metadata gap: characterization metadata (XRD/SEM/PL/UPS/XPS) is not reported in the table. Manual verification is recommended."
    )
]
