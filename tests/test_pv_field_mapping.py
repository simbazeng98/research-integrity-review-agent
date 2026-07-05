from __future__ import annotations

from integrity_agent.domains.photovoltaics.field_mapping import infer_pv_field_mapping

def test_pv_field_mapping_synonyms():
    # Voc checks
    for header in ["Voc", "V_oc", "V OC", "open circuit voltage", "open-circuit voltage", "voltage_oc", "VOC (V)", "Voc [V]"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map Voc synonym: {header}"
        assert m.canonical_field == "voc_v"

    # Jsc checks
    for header in ["Jsc", "J_SC", "J short circuit", "short-circuit current density", "current density", "mA cm-2", "mA/cm2", "mA/cm^2", "mA cm^-2"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map Jsc synonym: {header}"
        assert m.canonical_field == "jsc_ma_cm2"

    # FF checks
    for header in ["FF", "fill factor", "Fill Factor (%)", "fill_factor", "ff (%)"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map FF synonym: {header}"
        assert m.canonical_field == "ff"

    # PCE checks
    for header in ["PCE", "Efficiency", "efficiency (%)", "eta", "η", "power conversion efficiency"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map PCE synonym: {header}"
        assert m.canonical_field == "pce_percent"

    # EQE Jsc checks
    for header in ["EQE Jsc", "Jsc_EQE", "integrated Jsc", "integrated current density", "Jsc from EQE", "Jsc from IPCE", "IPCE Jsc"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map EQE Jsc synonym: {header}"
        assert m.canonical_field == "eqe_jsc_ma_cm2"

    # Bandgap checks
    for header in ["Eg", "E_g", "bandgap", "band gap", "bandgap (eV)"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map Bandgap synonym: {header}"
        assert m.canonical_field == "bandgap_ev"

    # Area checks
    for header in ["active area", "aperture area", "mask area", "device area", "area cm2", "area (cm^2)"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map Area synonym: {header}"
        assert m.canonical_field in ("active_area_cm2", "aperture_area_cm2", "mask_area_cm2")

    # Scan & Stability checks
    for header in ["scan direction", "scan rate", "mV/s", "T80", "stability", "MPP", "encapsulation"]:
        m = infer_pv_field_mapping(header)
        assert m is not None, f"Failed to map Scan/Stability synonym: {header}"
        assert m.canonical_field in ("scan_direction", "scan_rate", "t80_h", "mpp_tracking", "encapsulation")

def test_pv_field_mapping_ambiguous():
    # Ambiguous names should not map
    for header in ["current", "voltage", "area", "v", "j", "power", "density"]:
        m = infer_pv_field_mapping(header)
        assert m is None, f"Ambiguous name mapped: {header}"
