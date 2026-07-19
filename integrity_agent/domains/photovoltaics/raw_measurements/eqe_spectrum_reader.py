from __future__ import annotations

import re
from pathlib import Path
from integrity_agent.domains.photovoltaics.raw_measurements.schema import EQESpectrum

def read_eqe_spectrum_file(path: str, metadata: dict | None = None) -> EQESpectrum:
    if metadata is None:
        metadata = {}

    warnings = []
    filepath = Path(path)
    filename = filepath.name
    spectrum_id = f"eqe-{filepath.stem}"

    # Guess device id
    device_id = metadata.get("device_id")
    if not device_id:
        fn_stem = filepath.stem
        parts = re.split(r"[-_]", fn_stem)
        for part in parts:
            if "dev" in part.lower():
                device_id = part
                break
        if not device_id:
            device_id = parts[0] if parts else filepath.stem

    # Open file
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return EQESpectrum(
            spectrum_id=spectrum_id,
            source_file=filename,
            wavelength_nm=[],
            eqe_fraction=[],
            device_id_guess=device_id,
            warnings=[f"Failed to open file: {e}"]
        )

    if not lines:
        return EQESpectrum(
            spectrum_id=spectrum_id,
            source_file=filename,
            wavelength_nm=[],
            eqe_fraction=[],
            device_id_guess=device_id,
            warnings=["File is empty"]
        )

    # Detect delimiter
    header_line = lines[0]
    delimiters = [",", "\t", ";"]
    best_delim = None
    max_cols = 0
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
            # try to find a header line containing keywords
            header_idx = -1
            for idx, line in enumerate(lines):
                line_lower = line.lower()
                if any(k in line_lower for k in ("wavelength", "nm", "eqe", "ipce")):
                    header_idx = idx
                    break
            if header_idx != -1:
                header_line = lines[header_idx]
                lines = lines[header_idx:]
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
                best_delim = None

    # Check if first line is a header
    def is_numeric(s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False

    first_line_cols = [c.strip() for c in header_line.split(best_delim) if c.strip()] if best_delim else [c.strip() for c in header_line.split() if c.strip()]
    has_header = any(not is_numeric(c) for c in first_line_cols)

    headers = []
    data_start_idx = 1
    if has_header:
        headers = [c.lower() for c in first_line_cols]
        data_start_idx = 1
    else:
        headers = ["wavelength", "eqe"]
        data_start_idx = 0

    # Map headers
    w_idx = -1
    eqe_idx = -1
    for idx, h in enumerate(headers):
        if any(k in h for k in ("wavelength", "lambda", "nm")):
            if w_idx == -1:
                w_idx = idx
        elif any(k in h for k in ("eqe", "ipce", "efficiency")):
            if eqe_idx == -1:
                eqe_idx = idx

    if w_idx == -1:
        w_idx = 0
        warnings.append("Could not identify wavelength column; assumed column 0.")
    if eqe_idx == -1:
        eqe_idx = 1
        warnings.append("Could not identify EQE column; assumed column 1.")

    # Parse rows
    wavelengths = []
    eqe_raw = []
    
    for line_idx in range(data_start_idx, len(lines)):
        line = lines[line_idx]
        if line.startswith("#") or line.startswith("//"):
            continue
        parts = [p.strip() for p in line.split(best_delim) if p.strip()] if best_delim else [p.strip() for p in line.split() if p.strip()]
        if len(parts) <= max(w_idx, eqe_idx):
            continue
        try:
            w_val = float(parts[w_idx])
            eqe_val = float(parts[eqe_idx])
            wavelengths.append(w_val)
            eqe_raw.append(eqe_val)
        except (ValueError, IndexError):
            continue

    if not wavelengths:
        return EQESpectrum(
            spectrum_id=spectrum_id,
            source_file=filename,
            wavelength_nm=[],
            eqe_fraction=[],
            device_id_guess=device_id,
            warnings=warnings + ["No data parsed from file"]
        )

    # Check for non-monotonic wavelength
    is_asc = all(wavelengths[i] <= wavelengths[i+1] for i in range(len(wavelengths)-1))
    is_desc = all(wavelengths[i] >= wavelengths[i+1] for i in range(len(wavelengths)-1))
    if not (is_asc or is_desc):
        warnings.append("non-monotonic wavelength")

    # Wavelength unit conversion: check if in um
    # E.g. if max(wavelengths) < 10.0 (like 0.3 to 1.1 um)
    max_w = max(wavelengths)
    if max_w < 10.0:
        wavelengths = [w * 1000.0 for w in wavelengths]
        warnings.append("wavelength converted from um to nm")

    # EQE unit conversion: check if percent vs fraction
    # E.g. check if values are mostly > 1.0 (some EQE could be very small, but champion EQE is typically > 10%)
    max_eqe = max(eqe_raw)
    eqe_fraction = []
    
    if max_eqe > 1.0:
        # Convert percent to fraction
        eqe_fraction = [e / 100.0 for e in eqe_raw]
        # Re-check max after conversion
        if max(eqe_fraction) > 1.05:
            warnings.append("eqe values outside 0–1 after conversion")
    else:
        eqe_fraction = eqe_raw
        
    if any(e < -0.05 for e in eqe_fraction):
        warnings.append("eqe values outside 0–1 after conversion")

    # Warning: too few points
    if len(wavelengths) < 10:
        warnings.append("too few points")

    # Warning: range too narrow
    w_min = min(wavelengths)
    w_max = max(wavelengths)
    if (w_max - w_min) < 100.0:
        warnings.append("wavelength range too narrow")

    return EQESpectrum(
        spectrum_id=spectrum_id,
        source_file=filename,
        wavelength_nm=wavelengths,
        eqe_fraction=eqe_fraction,
        device_id_guess=device_id,
        warnings=warnings
    )
