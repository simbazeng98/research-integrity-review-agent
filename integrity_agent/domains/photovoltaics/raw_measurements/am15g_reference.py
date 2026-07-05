from __future__ import annotations

import os
from pathlib import Path

# Built-in toy AM1.5G spectrum for testing/fallback
TOY_AM15G_SPECTRUM = [
    (300.0, 0.1), (350.0, 0.5), (400.0, 1.0), (450.0, 1.2), (500.0, 1.4),
    (550.0, 1.3), (600.0, 1.2), (650.0, 1.1), (700.0, 1.0), (750.0, 0.9),
    (800.0, 0.8), (850.0, 0.7), (900.0, 0.6), (950.0, 0.4), (1000.0, 0.3),
    (1100.0, 0.2), (1200.0, 0.1)
]

def load_reference_spectrum(path_or_name: str | None = None) -> tuple[list[tuple[float, float]], list[str]]:
    warnings = []
    
    if not path_or_name:
        # Default path
        project_root = Path(__file__).resolve().parents[4]
        path_or_name = str(project_root / "examples" / "toy_raw_pv_package" / "reference" / "toy_am15g.csv")
        
    filepath = Path(path_or_name)
    
    if not filepath.exists() or filepath.is_dir():
        warnings.append(f"Reference file '{path_or_name}' not found; using embedded toy AM1.5G spectrum.")
        return TOY_AM15G_SPECTRUM, warnings

    spectrum = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            warnings.append("Reference file is empty; using embedded toy AM1.5G spectrum.")
            return TOY_AM15G_SPECTRUM, warnings
            
        # Parse headers/rows
        header_mapped = False
        w_idx = 0
        irr_idx = 1
        
        first_line = lines[0]
        # check if it is header
        parts = [p.strip() for p in first_line.split(",") if p.strip()]
        if not parts:
            parts = [p.strip() for p in first_line.split() if p.strip()]
            
        def is_num(s: str) -> bool:
            try:
                float(s)
                return True
            except ValueError:
                return False
                
        has_header = any(not is_num(p) for p in parts)
        start_idx = 1 if has_header else 0
        
        if has_header:
            headers = [h.lower() for h in parts]
            for idx, h in enumerate(headers):
                if "wavelength" in h or "nm" in h:
                    w_idx = idx
                elif "irradiance" in h or "w_m2" in h or "intensity" in h:
                    irr_idx = idx
                    
        for line_idx in range(start_idx, len(lines)):
            line = lines[line_idx]
            row_parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(row_parts) <= max(w_idx, irr_idx):
                row_parts = [p.strip() for p in line.split() if p.strip()]
            if len(row_parts) <= max(w_idx, irr_idx):
                continue
            try:
                w_val = float(row_parts[w_idx])
                irr_val = float(row_parts[irr_idx])
                spectrum.append((w_val, irr_val))
            except ValueError:
                continue
                
        if not spectrum:
            warnings.append("No valid data parsed from reference file; using embedded toy AM1.5G spectrum.")
            return TOY_AM15G_SPECTRUM, warnings
            
        # Ensure it's sorted
        spectrum.sort(key=lambda item: item[0])
        return spectrum, warnings
        
    except Exception as e:
        warnings.append(f"Failed to read reference spectrum: {e}; using embedded toy AM1.5G spectrum.")
        return TOY_AM15G_SPECTRUM, warnings
