from __future__ import annotations

import os
import re
from pathlib import Path
from integrity_agent.domains.photovoltaics.raw_measurements.schema import JVCurve

def read_jv_curve_file(path: str, metadata: dict | None = None) -> JVCurve:
    if metadata is None:
        metadata = {}

    warnings = []
    filepath = Path(path)
    filename = filepath.name
    curve_id = f"jv-{filepath.stem}"

    # Guess scan direction
    scan_dir = "unknown"
    meta_dir = metadata.get("scan_direction") or metadata.get("direction")
    if meta_dir:
        meta_dir_lower = str(meta_dir).lower()
        if "forward" in meta_dir_lower or "fwd" in meta_dir_lower:
            scan_dir = "forward"
        elif "reverse" in meta_dir_lower or "rev" in meta_dir_lower:
            scan_dir = "reverse"
    else:
        fn_lower = filename.lower()
        if "forward" in fn_lower or "fwd" in fn_lower:
            scan_dir = "forward"
        elif "reverse" in fn_lower or "rev" in fn_lower:
            scan_dir = "reverse"

    # Guess device id
    device_id = metadata.get("device_id")
    if not device_id:
        # try to parse from filename. e.g. dev1_fwd.csv -> dev1
        fn_stem = filepath.stem
        # split by underscore/dash
        parts = re.split(r"[-_]", fn_stem)
        for part in parts:
            if "dev" in part.lower():
                device_id = part
                break
        if not device_id:
            device_id = parts[0] if parts else filepath.stem

    # Read lines
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return JVCurve(
            curve_id=curve_id,
            source_file=filename,
            voltage_v=[],
            current_density_ma_cm2=[],
            scan_direction=scan_dir,
            device_id_guess=device_id,
            warnings=[f"Failed to open file: {e}"]
        )

    if not lines:
        return JVCurve(
            curve_id=curve_id,
            source_file=filename,
            voltage_v=[],
            current_density_ma_cm2=[],
            scan_direction=scan_dir,
            device_id_guess=device_id,
            warnings=["File is empty"]
        )

    # Detect delimiter using header or first line
    header_line = lines[0]
    delimiters = [",", "\t", ";"]
    best_delim = None
    max_cols = 0
    for d in delimiters:
        cols = [c.strip() for c in header_line.split(d) if c.strip()]
        if len(cols) > max_cols:
            max_cols = len(cols)
            best_delim = d

    # If no delimiter detected, fallback to whitespace splitting
    if max_cols <= 1:
        cols = [c.strip() for c in header_line.split() if c.strip()]
        if len(cols) > 1:
            best_delim = None  # None indicates whitespace splitting
        else:
            # Maybe the file has comments before the header. Let's find first line with numbers
            # or try to find a header line.
            # E.g. find a line containing voltage/current keywords
            header_idx = -1
            for idx, line in enumerate(lines):
                line_lower = line.lower()
                if any(k in line_lower for k in ("volt", "bias", "current", "jsc", "density", "pce")):
                    header_idx = idx
                    break
            if header_idx != -1:
                header_line = lines[header_idx]
                lines = lines[header_idx:]
                # re-evaluate delimiter
                for d in delimiters:
                    cols = [c.strip() for c in header_line.split(d) if c.strip()]
                    if len(cols) > max_cols:
                        max_cols = len(cols)
                        best_delim = d
                if max_cols <= 1:
                    cols = [c.strip() for c in header_line.split() if c.strip()]
                    if len(cols) > 1:
                        best_delim = None
            else:
                # No header found, assume no headers, first line is data, space split
                best_delim = None

    # Parse headers
    headers = []
    data_start_idx = 1
    
    # Let's check if first line is indeed a header (contains non-numeric characters)
    def is_numeric(s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False

    first_line_cols = [c.strip() for c in header_line.split(best_delim) if c.strip()] if best_delim else [c.strip() for c in header_line.split() if c.strip()]
    has_header = any(not is_numeric(c) for c in first_line_cols)

    if has_header:
        headers = [c.lower() for c in first_line_cols]
        data_start_idx = 1
    else:
        # no header, just assume first col is Voltage, second is Current Density
        headers = ["voltage", "current_density"]
        data_start_idx = 0

    # Parse rows
    voltages = []
    currents = []
    
    for line_idx in range(data_start_idx, len(lines)):
        line = lines[line_idx]
        if line.startswith("#") or line.startswith("//"):
            continue # comment line
        parts = [p.strip() for p in line.split(best_delim) if p.strip()] if best_delim else [p.strip() for p in line.split() if p.strip()]
        if len(parts) < 2:
            continue
        try:
            v_val = float(parts[0] if len(parts) >= 1 else 0)
            c_val = float(parts[1] if len(parts) >= 2 else 0)
            # Store raw values for now, mapping will happen later
            voltages.append(v_val)
            currents.append(c_val)
        except ValueError:
            # skip row with non-numeric data
            continue

    # Let's map headers to columns
    v_idx = -1
    j_idx = -1
    i_idx = -1

    for idx, h in enumerate(headers):
        # Voltage synonyms
        if any(k in h for k in ("volt", "bias", "potential")) or h == "v":
            if v_idx == -1:
                v_idx = idx
        # Current Density synonyms
        elif any(k in h for k in ("density", "jsc", "ma/cm", "ma cm")) or h == "j":
            if j_idx == -1:
                j_idx = idx
        # Current synonyms
        elif any(k in h for k in ("current", "ma", "amper")) or h == "i" or h == "a":
            if i_idx == -1:
                i_idx = idx

    # If headers not empty and we didn't map correctly, try index order: 0 -> V, 1 -> J/I
    if v_idx == -1:
        v_idx = 0
        warnings.append("Could not identify voltage column header; assumed column 0.")
    if j_idx == -1 and i_idx == -1:
        if len(headers) >= 2:
            j_idx = 1
            warnings.append("Could not identify current/density column header; assumed column 1 as current density.")
        else:
            warnings.append("Could not find current or density column.")

    # Now extract the lists
    volt_list = []
    curr_list = []

    # re-parse according to correct indices
    voltages = []
    current_density_or_current = []
    
    target_idx = j_idx if j_idx != -1 else i_idx
    if target_idx == -1:
        target_idx = 1

    for line_idx in range(data_start_idx, len(lines)):
        line = lines[line_idx]
        if line.startswith("#") or line.startswith("//"):
            continue
        parts = [p.strip() for p in line.split(best_delim) if p.strip()] if best_delim else [p.strip() for p in line.split() if p.strip()]
        if len(parts) <= max(v_idx, target_idx):
            continue
        try:
            v_val = float(parts[v_idx])
            c_val = float(parts[target_idx])
            voltages.append(v_val)
            current_density_or_current.append(c_val)
        except (ValueError, IndexError):
            continue

    # Conversions
    final_density = []
    active_area = metadata.get("active_area_cm2") or metadata.get("area") or metadata.get("active_area")
    
    is_current_only = (j_idx == -1 and i_idx != -1)
    
    # Check if header explicitly specifies unit
    target_header = headers[target_idx] if len(headers) > target_idx else ""
    is_a_unit = "a" in target_header and "ma" not in target_header and "cm" not in target_header

    for c_val in current_density_or_current:
        # Convert A to mA if needed
        val_ma = c_val
        if is_a_unit:
            val_ma = c_val * 1000.0
            
        if is_current_only:
            if active_area:
                try:
                    area_val = float(active_area)
                    if area_val > 0:
                        final_density.append(val_ma / area_val)
                    else:
                        final_density.append(val_ma)
                except ValueError:
                    final_density.append(val_ma)
            else:
                final_density.append(val_ma)
        else:
            final_density.append(val_ma)

    if is_current_only:
        if active_area:
            warnings.append(f"Converted current to current density using active area {active_area} cm².")
        else:
            warnings.append("Current column detected but no active area provided; J values contain raw currents in mA.")

    if is_a_unit:
        warnings.append("Converted current unit from A to mA.")

    # Return curve
    return JVCurve(
        curve_id=curve_id,
        source_file=filename,
        voltage_v=voltages,
        current_density_ma_cm2=final_density,
        scan_direction=scan_dir,
        device_id_guess=device_id,
        warnings=warnings
    )
