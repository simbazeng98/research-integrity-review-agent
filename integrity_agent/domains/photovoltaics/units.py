from __future__ import annotations

import re

def to_float(val) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        # Remove any brackets, % symbol or extraneous whitespace
        cleaned = str(val).strip()
        cleaned = re.sub(r'[^\d\.\-eE]', '', cleaned)
        if not cleaned:
            return None
        return float(cleaned)
    except ValueError:
        return None

def normalize_voc(value, unit_hint) -> tuple[float | None, list[str]]:
    val = to_float(value)
    if val is None:
        return None, ["Could not parse Voc value as numeric"]
    warnings = []
    if unit_hint == "mv":
        return val / 1000.0, warnings
    if val > 20 and not unit_hint:
        warnings.append(f"Voc value {val} is greater than 20 but unit hint is missing. Assuming it might be in mV but not converting automatically.")
        return val, warnings
    return val, warnings

def normalize_jsc(value, unit_hint) -> tuple[float | None, list[str]]:
    val = to_float(value)
    if val is None:
        return None, ["Could not parse Jsc value as numeric"]
    warnings = []
    if unit_hint == "a/m2":
        warnings.append(f"Converting Jsc {val} from A/m2 to mA/cm2 (factor of 0.1)")
        return val * 0.1, warnings
    if unit_hint == "a/cm2":
        warnings.append(f"Converting Jsc {val} from A/cm2 to mA/cm2 (factor of 1000)")
        return val * 1000.0, warnings
    return val, warnings

def normalize_ff(value, unit_hint) -> tuple[float | None, str, list[str]]:
    val = to_float(value)
    if val is None:
        return None, "unknown", ["Could not parse FF value as numeric"]
    warnings = []
    if unit_hint == "%" or (val > 1.0 and val <= 100.0):
        if not unit_hint:
            warnings.append(f"FF value {val} treated as percent and converted to fraction.")
        return val / 100.0, "%", warnings
    if val <= 1.0:
        return val, "fraction", warnings
    if val > 100.0:
        warnings.append(f"FF value {val} is > 100, which is physically implausible.")
        return val, "unknown", warnings
    return val, "unknown", warnings

def normalize_pce(value, unit_hint) -> tuple[float | None, list[str]]:
    val = to_float(value)
    if val is None:
        return None, ["Could not parse PCE value as numeric"]
    warnings = []
    if unit_hint == "fraction" or (val >= 0.0 and val <= 1.0):
        warnings.append(f"PCE value {val} appears to be reported as fraction. Converting to percentage.")
        return val * 100.0, warnings
    if val > 100.0:
        warnings.append(f"PCE value {val} is > 100%, which is physically implausible.")
        return val, warnings
    return val, warnings

def normalize_area(value, unit_hint) -> tuple[float | None, list[str]]:
    val = to_float(value)
    if val is None:
        return None, ["Could not parse area value as numeric"]
    warnings = []
    if unit_hint == "mm2":
        warnings.append(f"Converting area {val} from mm2 to cm2 (factor of 0.01)")
        return val * 0.01, warnings
    return val, warnings

def normalize_light_intensity(value, unit_hint) -> tuple[float | None, list[str]]:
    val = to_float(value)
    if val is None:
        return None, ["Could not parse light intensity value as numeric"]
    warnings = []
    if unit_hint == "w/m2":
        warnings.append(f"Converting light intensity {val} from W/m2 to mW/cm2 (factor of 0.1)")
        val *= 0.1
    if val <= 0:
        return None, [*warnings, "Light intensity must be a positive numeric value"]
    return val, warnings

def normalize_bandgap(value, unit_hint) -> tuple[float | None, list[str]]:
    val = to_float(value)
    if val is None:
        return None, ["Could not parse bandgap value as numeric"]
    warnings = []
    if unit_hint == "nm":
        warnings.append(f"Bandgap value {val} is in nm. Auto-conversion to eV is not implemented in v0.10.")
    return val, warnings
