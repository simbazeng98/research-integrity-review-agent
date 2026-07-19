from __future__ import annotations

import re

from integrity_agent.domains.photovoltaics.schema import PVMetricRow, PVConsistencyFinding


def _header_contains_alias(header: str, alias: str) -> bool:
    """Return whether *alias* occurs as a complete token sequence in a header."""
    header_tokens = re.findall(r"[a-z0-9]+", header.lower())
    alias_tokens = re.findall(r"[a-z0-9]+", alias.lower())
    alias_size = len(alias_tokens)
    return bool(alias_tokens) and any(
        header_tokens[index:index + alias_size] == alias_tokens
        for index in range(len(header_tokens) - alias_size + 1)
    )

def run_materials_characterization_check(rows: list[PVMetricRow]) -> list[PVConsistencyFinding]:
    findings: list[PVConsistencyFinding] = []
    
    # Group rows by table_id
    tables_rows: dict[str, list[PVMetricRow]] = {}
    for row in rows:
        tables_rows.setdefault(row.table_id, []).append(row)

    finding_idx = 1

    for table_id, t_rows in tables_rows.items():
        source_file = t_rows[0].source_file
        # A filename or sheet name can provide review context, but cannot by
        # itself establish that a table contains characterization data. Only
        # explicit column-header tokens/aliases may trigger a finding.
        raw_cols = list(t_rows[0].raw_values.keys())
        raw_cols_lower = [c.lower() for c in raw_cols]

        def has_keyword(*aliases: str) -> bool:
            return any(
                _header_contains_alias(column, alias)
                for column in raw_cols
                for alias in aliases
            )

        # XRD check
        if has_keyword("xrd", "2theta", "2-theta", "diffraction"):
            has_source = any(any(k in col for k in ("source", "radiation", "cu", "ka", "wavelength")) for col in raw_cols_lower)
            has_rate = any(any(k in col for k in ("rate", "step", "speed")) for col in raw_cols_lower)
            missing = []
            if not has_source:
                missing.append("radiation source (e.g. Cu Ka)")
            if not has_rate:
                missing.append("scan rate or step size")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "XRD", missing, 
                    "radiation source, 2theta range, scan rate / step size", raw_cols
                ))
                finding_idx += 1

        # XPS check
        if has_keyword("xps", "binding energy", "photoelectron"):
            has_calib = any(any(k in col for k in ("calib", "reference", "charge", "c1s", "fitting")) for col in raw_cols_lower)
            missing = []
            if not has_calib:
                missing.append("calibration reference / binding energy correction (e.g. C 1s at 284.8 eV)")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "XPS", missing,
                    "calibration reference, binding energy correction, peak fitting method", raw_cols
                ))
                finding_idx += 1

        # PL/TRPL check
        if has_keyword("pl", "trpl", "photoluminescence", "lifetime", "decay"):
            has_exc = any(any(k in col for k in ("excitation", "laser", "fluence", "power")) for col in raw_cols_lower)
            missing = []
            if not has_exc:
                missing.append("excitation wavelength or laser fluence/power")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "PL/TRPL", missing,
                    "excitation wavelength, fluence/power, detector settings", raw_cols
                ))
                finding_idx += 1

        # UV-vis check
        if has_keyword("uv-vis", "uv_vis", "absorbance", "absorption", "transmission"):
            has_baseline = any(any(k in col for k in ("baseline", "substrate", "reference", "blank")) for col in raw_cols_lower)
            missing = []
            if not has_baseline:
                missing.append("substrate reference or baseline calibration details")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "UV-vis/Absorbance", missing,
                    "substrate/baseline, integration method if bandgap derived", raw_cols
                ))
                finding_idx += 1

        # SEM/TEM check
        if has_keyword("sem", "tem", "micrograph", "transmission electron"):
            has_scale = any(any(k in col for k in ("scale", "bar", "magnification", "voltage", "kv")) for col in raw_cols_lower)
            missing = []
            if not has_scale:
                missing.append("scale bar calibration or accelerating voltage (kV)")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "SEM/TEM", missing,
                    "scale bar / magnification / accelerating voltage", raw_cols
                ))
                finding_idx += 1

        # AFM check
        if has_keyword("afm", "roughness", "rms", "microscopy"):
            has_size = any(any(k in col for k in ("size", "area", "roughness", "scan", "rms", "rq")) for col in raw_cols_lower)
            missing = []
            if not has_size:
                missing.append("AFM scan size or surface roughness metrics (RMS / Ra)")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "AFM", missing,
                    "scan size, roughness metric", raw_cols
                ))
                finding_idx += 1

        # GIWAXS check
        if has_keyword("giwaxs", "grazing incidence"):
            has_angle = any(any(k in col for k in ("angle", "incidence", "wavelength", "beam")) for col in raw_cols_lower)
            missing = []
            if not has_angle:
                missing.append("incidence angle or beam energy/wavelength")
            
            if missing:
                findings.append(make_mc_finding(
                    finding_idx, table_id, source_file, "GIWAXS", missing,
                    "incidence angle, beam energy/wavelength", raw_cols
                ))
                finding_idx += 1

    return findings

def make_mc_finding(
    idx: int,
    table_id: str,
    source_file: str,
    char_type: str,
    missing: list[str],
    expected: str,
    raw_cols: list[str]
) -> PVConsistencyFinding:
    observed = {
        "characterization_type": char_type,
        "missing_metadata": missing,
        "parsed_columns": raw_cols
    }
    
    safe_lang = (
        f"Materials characterization reporting completeness signal: parsed {char_type} metadata appears incomplete. "
        f"Missing: {', '.join(missing)}. This does not determine manipulation; "
        f"it identifies missing context required for reproducibility and interpretation."
    )

    evidence_items = [{
        "location": f"Table {table_id}",
        "message": f"Table '{source_file}' contains {char_type} data but lacks recommended metadata details: {', '.join(missing)}."
    }]

    return PVConsistencyFinding(
        finding_id=f"PV-MAT-FIND-{idx:03d}",
        rule_id="pv_materials_characterization_metadata",
        detector_id="materials_characterization",
        risk_level="low",
        risk_ceiling="low",
        source_file=source_file,
        table_id=table_id,
        row_index=None,
        device_id=None,
        observed_values=observed,
        recomputed_values={},
        tolerance=None,
        evidence_items=evidence_items,
        safe_report_language=safe_lang,
        alternative_explanations=[
            "Instrument settings and calibrations are described in the manuscript methods text rather than the source table",
            "Data was collected by a third-party facility with standard setup parameters not reported in the summary",
            "Columns represent peak lists or extracted parameters rather than raw spectral outputs"
        ],
        false_positive_risks=[
            "Non-standard reporting styles or abbreviated column names used by the authors",
            "The metadata is mentioned in figure captions or supplementary captions not parsed by the tool"
        ],
        manual_verification=[
            "Inspect the manuscript Methods section and Supplementary Information for instrument metadata",
            "Verify the original instrument raw files (.raw, .txt, .xrdml, etc.) for embedded header metadata",
            "Confirm the calibration references and fitting scripts used for peak extraction"
        ],
        limitations=[
            "Limited to analyzing structured data tables and column header names"
        ],
        metadata={
            "characterization_type": char_type,
            "missing_items": missing,
            "expected_items_hint": expected
        }
    )
