from __future__ import annotations

import re
import sys
from integrity_agent.domains.photovoltaics.schema import PVFieldMapping

# Regex lists for canonical field mapping
voc_exact = [r"\bvoc\b", r"\bv_oc\b", r"\bv oc\b"]
voc_phrase = [r"open[- ]circuit voltage", r"voltage[-_]oc", r"open circuit voltage", r"voltage oc"]

jsc_exact = [r"\bjsc\b", r"\bj_sc\b", r"\bj short circuit\b"]
jsc_phrase = [r"short[- ]circuit current density", r"current density", r"ma\s*cm[-^]*2", r"ma/cm2", r"ma/cm\^2", r"ma\s*cm\^-2"]

ff_exact = [r"\bff\b", r"\bfill[-_ ]factor\b"]
pce_exact = [r"\bpce\b", r"\bη\b", r"\beta\b"]
pce_phrase = [r"power conversion efficiency", r"efficiency"]

eqe_jsc_exact = [
    r"\beqe jsc\b", r"\bjsc_eqe\b", r"\bjsc eqe\b", 
    r"\bjsc[-_ ]from[-_ ]eqe\b", r"\bjsc[-_ ]from[-_ ]ipce\b", 
    r"\bipce jsc\b", r"\bintegrated jsc\b", r"\bintegrated current density\b"
]

eg_exact = [r"\beg\b", r"\be_g\b", r"\bbandgap\b", r"\bband gap\b"]

active_area_exact = [r"active area", r"active_area"]
generic_area_exact = [r"device area", r"device_area", r"cell area", r"cell_area", r"area cm2", r"area \(cm\^2\)", r"\barea\b"]
aperture_area_exact = [r"aperture area", r"aperture_area"]
mask_area_exact = [r"mask area", r"mask_area"]

scan_dir_exact = [r"scan direction", r"scan_direction", r"reverse scan", r"forward scan"]
scan_rate_exact = [r"scan rate", r"scan_rate", r"mv/s", r"scan speed"]
stabilized_pce_exact = [r"stabilized pce", r"stabilized_pce", r"stabilized efficiency", r"stabilized_efficiency", r"spo\b", r"stabilized power output"]
mpp_exact = [r"\bmpp\b", r"maximum power point", r"mpp tracking", r"mpp_tracking"]

temp_exact = [r"\btemp\b", r"\btemperature\b"]
humidity_exact = [r"\bhumidity\b", r"\brh\b"]
encap_exact = [r"\bencapsulation\b", r"\bencapsulated\b"]
isos_exact = [r"\bisos\b"]
t80_exact = [r"\bt80\b", r"\bt-80\b"]
dur_exact = [r"stability duration", r"duration", r"aging time", r"testing time", r"\bstability\b"]

def infer_pv_field_mapping(column_name: str) -> PVFieldMapping | None:
    col_clean = column_name.strip().lower()
    
    # Check for ambiguous columns first, and skip mapping
    # "current" and "voltage" are ambiguous unless accompanied by specific density/Jsc/Voc modifiers
    if col_clean in ("current", "voltage", "area", "v", "j", "power", "density"):
        print(f"WARNING: Column name '{column_name}' is ambiguous and will not be mapped to any canonical PV field.", file=sys.stderr)
        return None

    def matches_any(patterns, text):
        return any(re.search(pat, text) is not None for pat in patterns)

    # Unit hints extraction
    unit_hint = None
    if re.search(r'\bmv\b|\bmillivolt', col_clean):
        unit_hint = "mv"
    elif re.search(r'\bv\b|\bvolt', col_clean):
        unit_hint = "v"
    
    if re.search(r'ma/cm2|ma\s*cm-2|ma\s*cm\^-2|ma/cm\^2', col_clean):
        unit_hint = "ma/cm2"
    elif re.search(r'a/m2|a\s*m-2|a\s*m\^-2', col_clean):
        unit_hint = "a/m2"
    elif re.search(r'a/cm2|a\s*cm-2|a\s*cm\^-2', col_clean):
        unit_hint = "a/cm2"
        
    if '%' in col_clean or 'percent' in col_clean:
        if unit_hint is None:
            unit_hint = "%"
    elif 'fraction' in col_clean:
        if unit_hint is None:
            unit_hint = "fraction"

    if re.search(r'cm2|cm\^2', col_clean):
        if unit_hint is None:
            unit_hint = "cm2"
    elif re.search(r'mm2|mm\^2', col_clean):
        if unit_hint is None:
            unit_hint = "mm2"

    if re.search(r'\bev\b|electron[ -]volt', col_clean):
        unit_hint = "ev"
    elif re.search(r'\bnm\b|nanometer', col_clean):
        unit_hint = "nm"

    if re.search(r'\bhours?\b|\bhr\b|\bhrs\b|\bh\b', col_clean):
        if unit_hint is None:
            unit_hint = "h"
            
    if re.search(r'mv/s', col_clean):
        unit_hint = "mv/s"

    # EQE Jsc
    if matches_any(eqe_jsc_exact, col_clean):
        return PVFieldMapping(
            canonical_field="eqe_jsc_ma_cm2",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Voc
    if matches_any(voc_exact, col_clean) or matches_any([r"voc\s*\(", r"voc\s*\["], col_clean):
        return PVFieldMapping(
            canonical_field="voc_v",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )
    if matches_any(voc_phrase, col_clean):
        return PVFieldMapping(
            canonical_field="voc_v",
            matched_column=column_name,
            confidence=0.85,
            unit_hint=unit_hint
        )

    # Jsc
    if matches_any(jsc_exact, col_clean):
        return PVFieldMapping(
            canonical_field="jsc_ma_cm2",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )
    if matches_any(jsc_phrase, col_clean):
        if "eqe" in col_clean or "ipce" in col_clean or "integrated" in col_clean:
            return PVFieldMapping(
                canonical_field="eqe_jsc_ma_cm2",
                matched_column=column_name,
                confidence=0.85,
                unit_hint=unit_hint
            )
        return PVFieldMapping(
            canonical_field="jsc_ma_cm2",
            matched_column=column_name,
            confidence=0.85,
            unit_hint=unit_hint
        )

    # FF
    if matches_any(ff_exact, col_clean):
        return PVFieldMapping(
            canonical_field="ff",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )
    if "fill factor" in col_clean or "fill_factor" in col_clean:
        return PVFieldMapping(
            canonical_field="ff",
            matched_column=column_name,
            confidence=0.85,
            unit_hint=unit_hint
        )

    # PCE
    if matches_any(pce_exact, col_clean):
        return PVFieldMapping(
            canonical_field="pce_percent",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )
    if matches_any(pce_phrase, col_clean):
        return PVFieldMapping(
            canonical_field="pce_percent",
            matched_column=column_name,
            confidence=0.85,
            unit_hint=unit_hint
        )

    # Bandgap
    if matches_any(eg_exact, col_clean):
        return PVFieldMapping(
            canonical_field="bandgap_ev",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Aperture Area
    if matches_any(aperture_area_exact, col_clean):
        return PVFieldMapping(
            canonical_field="aperture_area_cm2",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Active Area
    if matches_any(active_area_exact, col_clean):
        return PVFieldMapping(
            canonical_field="active_area_cm2",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Mask Area
    if matches_any(mask_area_exact, col_clean):
        return PVFieldMapping(
            canonical_field="mask_area_cm2",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Generic Area
    if matches_any(generic_area_exact, col_clean):
        return PVFieldMapping(
            canonical_field="active_area_cm2",
            matched_column=column_name,
            confidence=0.85,
            unit_hint=unit_hint,
            notes="Mapped generic area to active_area_cm2"
        )

    # Scan direction
    if matches_any(scan_dir_exact, col_clean):
        return PVFieldMapping(
            canonical_field="scan_direction",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Scan rate
    if matches_any(scan_rate_exact, col_clean):
        return PVFieldMapping(
            canonical_field="scan_rate",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Stabilized PCE
    if matches_any(stabilized_pce_exact, col_clean):
        return PVFieldMapping(
            canonical_field="stabilized_pce_percent",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # MPP tracking
    if matches_any(mpp_exact, col_clean):
        return PVFieldMapping(
            canonical_field="mpp_tracking",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Temperature
    if matches_any(temp_exact, col_clean):
        return PVFieldMapping(
            canonical_field="temperature_c",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Humidity
    if matches_any(humidity_exact, col_clean):
        return PVFieldMapping(
            canonical_field="humidity_percent",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Encapsulation
    if matches_any(encap_exact, col_clean):
        return PVFieldMapping(
            canonical_field="encapsulation",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # ISOS protocol
    if matches_any(isos_exact, col_clean):
        return PVFieldMapping(
            canonical_field="isos_protocol",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # T80
    if matches_any(t80_exact, col_clean):
        return PVFieldMapping(
            canonical_field="t80_h",
            matched_column=column_name,
            confidence=0.95,
            unit_hint=unit_hint
        )

    # Stability Duration
    if matches_any(dur_exact, col_clean):
        return PVFieldMapping(
            canonical_field="t80_h",
            matched_column=column_name,
            confidence=0.65,
            unit_hint=unit_hint,
            notes="Mapped duration to t80_h as backup stability field"
        )

    return None
