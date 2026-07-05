from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

CANONICAL_FIELDS = {
    "voc_v",
    "jsc_ma_cm2",
    "ff",
    "pce_percent",
    "eqe_jsc_ma_cm2",
    "bandgap_ev",
    "active_area_cm2",
    "aperture_area_cm2",
    "scan_direction",
    "scan_rate",
    "stabilized_pce_percent",
    "mpp_tracking",
    "temperature_c",
    "humidity_percent",
    "encapsulation",
    "isos_protocol",
    "t80_h",
}

@dataclass
class PVMetricRow:
    row_id: str
    source_file: str
    table_id: str
    sheet_name: str | None = None
    row_index: int | None = None
    device_id: str | None = None
    sample_id: str | None = None
    condition_label: str | None = None
    architecture: str | None = None
    absorber: str | None = None
    bandgap_ev: float | None = None
    voc_v: float | None = None
    jsc_ma_cm2: float | None = None
    ff: float | None = None
    ff_unit: str | None = None
    pce_percent: float | None = None
    eqe_jsc_ma_cm2: float | None = None
    stabilized_pce_percent: float | None = None
    stabilized_power_output_percent: float | None = None
    reverse_scan_pce_percent: float | None = None
    forward_scan_pce_percent: float | None = None
    scan_direction: str | None = None
    scan_rate: float | None = None
    active_area_cm2: float | None = None
    aperture_area_cm2: float | None = None
    mask_area_cm2: float | None = None
    area_basis: str | None = None
    light_intensity_mw_cm2: float | None = None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    encapsulation: str | None = None
    mpp_tracking: str | None = None
    stability_duration_h: float | None = None
    t80_h: float | None = None
    isos_protocol: str | None = None
    raw_values: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PVFieldMapping:
    canonical_field: str
    matched_column: str
    confidence: float
    unit_hint: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PVConsistencyFinding:
    finding_id: str
    rule_id: str
    detector_id: str
    risk_level: str
    risk_ceiling: str
    source_file: str
    table_id: str
    row_index: int | list[int] | None = None
    device_id: str | None = None
    observed_values: dict[str, Any] = field(default_factory=dict)
    recomputed_values: dict[str, Any] = field(default_factory=dict)
    tolerance: Any = None
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    safe_report_language: str = ""
    alternative_explanations: list[str] = field(default_factory=list)
    false_positive_risks: list[str] = field(default_factory=list)
    manual_verification: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_pv_metric_rows(table_manifest_path: str | Path, column_profiles_path: str | Path | None = None) -> list[PVMetricRow]:
    from pathlib import Path
    import sys
    import json
    from integrity_agent.core.tables.table_reader import read_any_table
    from integrity_agent.core.tables.table_schema import TableManifestItem
    from integrity_agent.domains.photovoltaics.field_mapping import infer_pv_field_mapping
    from integrity_agent.domains.photovoltaics.units import (
        normalize_voc, normalize_jsc, normalize_ff, normalize_pce, normalize_area, normalize_bandgap, to_float
    )

    table_manifest_path = Path(table_manifest_path)
    if not table_manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {table_manifest_path}")

    # Load manifest items
    items: list[TableManifestItem] = []
    with table_manifest_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(TableManifestItem(**json.loads(line)))

    # Load column profiles if provided
    profiles_dict = {}
    if column_profiles_path:
        column_profiles_path = Path(column_profiles_path)
        if column_profiles_path.exists():
            with column_profiles_path.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        table_id = data.get("table_id")
                        prof = data.get("profile", {})
                        col_name = prof.get("column_name")
                        if table_id and col_name:
                            profiles_dict[(table_id, col_name)] = prof

    pv_rows: list[PVMetricRow] = []
    project_root = Path.cwd()

    for item in items:
        # Resolve target table file path
        file_path = Path(item.relative_path)
        if not file_path.is_absolute():
            file_path = (project_root / item.relative_path).resolve()

        if not file_path.exists():
            # Try fallbacks
            fallback = (project_root / "examples" / "toy_pv_package" / Path(item.relative_path).name).resolve()
            if fallback.exists():
                file_path = fallback
            else:
                fallback_table = (project_root / "examples" / "toy_table_package" / Path(item.relative_path).name).resolve()
                if fallback_table.exists():
                    file_path = fallback_table
                else:
                    print(f"WARNING: File not found: {item.relative_path}, skipping.", file=sys.stderr)
                    continue

        try:
            rows, cols, table_warnings = read_any_table(file_path, sheet_name=item.sheet_name)
        except Exception as e:
            print(f"ERROR: Failed to read table {file_path}: {e}", file=sys.stderr)
            continue

        # Map columns
        mappings: dict[int, PVFieldMapping] = {}
        device_id_col_idx = None
        sample_id_col_idx = None
        condition_col_idx = None
        absorber_col_idx = None
        architecture_col_idx = None

        for col_idx, col_name in enumerate(cols):
            mapping = infer_pv_field_mapping(col_name)
            prof = profiles_dict.get((item.table_id, col_name), {})
            unit_hint = prof.get("unit_hint")
            
            if mapping:
                if unit_hint and not mapping.unit_hint:
                    mapping = PVFieldMapping(
                        canonical_field=mapping.canonical_field,
                        matched_column=mapping.matched_column,
                        confidence=mapping.confidence,
                        unit_hint=unit_hint,
                        notes=mapping.notes
                    )
                mappings[col_idx] = mapping
            else:
                col_lower = col_name.lower()
                if any(x in col_lower for x in ("device id", "device_id", "device_name", "device name", "device#", "device no")) or col_lower == "device":
                    device_id_col_idx = col_idx
                elif any(x in col_lower for x in ("sample id", "sample_id", "sample_name", "sample name", "sample#")) or col_lower == "sample":
                    sample_id_col_idx = col_idx
                elif any(x in col_lower for x in ("condition", "group", "label")):
                    condition_col_idx = col_idx
                elif any(x in col_lower for x in ("absorber", "perovskite", "material")):
                    absorber_col_idx = col_idx
                elif any(x in col_lower for x in ("architecture", "structure")):
                    architecture_col_idx = col_idx

        # Build PVMetricRow for each row
        for r_idx, row in enumerate(rows):
            row_num = r_idx + 1
            row_id = f"{item.table_id}-row-{row_num}"
            raw_values = {}
            for col_idx, col_name in enumerate(cols):
                if col_idx < len(row):
                    raw_values[col_name] = row[col_idx]
                else:
                    raw_values[col_name] = None

            fields_data = {
                "row_id": row_id,
                "source_file": item.source_file,
                "table_id": item.table_id,
                "sheet_name": item.sheet_name,
                "row_index": row_num,
                "raw_values": raw_values,
                "warnings": []
            }

            if device_id_col_idx is not None and device_id_col_idx < len(row) and row[device_id_col_idx] is not None:
                fields_data["device_id"] = str(row[device_id_col_idx]).strip()
            if sample_id_col_idx is not None and sample_id_col_idx < len(row) and row[sample_id_col_idx] is not None:
                fields_data["sample_id"] = str(row[sample_id_col_idx]).strip()
            if condition_col_idx is not None and condition_col_idx < len(row) and row[condition_col_idx] is not None:
                fields_data["condition_label"] = str(row[condition_col_idx]).strip()
            if absorber_col_idx is not None and absorber_col_idx < len(row) and row[absorber_col_idx] is not None:
                fields_data["absorber"] = str(row[absorber_col_idx]).strip()
            if architecture_col_idx is not None and architecture_col_idx < len(row) and row[architecture_col_idx] is not None:
                fields_data["architecture"] = str(row[architecture_col_idx]).strip()

            for col_idx, mapping in mappings.items():
                if col_idx >= len(row):
                    continue
                val_str = row[col_idx]
                if val_str is None or str(val_str).strip() == "":
                    continue

                canonical = mapping.canonical_field
                unit_hint = mapping.unit_hint

                if canonical == "voc_v":
                    norm_val, warn = normalize_voc(val_str, unit_hint)
                    fields_data["voc_v"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "jsc_ma_cm2":
                    norm_val, warn = normalize_jsc(val_str, unit_hint)
                    fields_data["jsc_ma_cm2"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "ff":
                    norm_val, ff_unit, warn = normalize_ff(val_str, unit_hint)
                    fields_data["ff"] = norm_val
                    fields_data["ff_unit"] = ff_unit
                    fields_data["warnings"].extend(warn)
                elif canonical == "pce_percent":
                    norm_val, warn = normalize_pce(val_str, unit_hint)
                    fields_data["pce_percent"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "eqe_jsc_ma_cm2":
                    norm_val, warn = normalize_jsc(val_str, unit_hint)
                    fields_data["eqe_jsc_ma_cm2"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "bandgap_ev":
                    norm_val, warn = normalize_bandgap(val_str, unit_hint)
                    fields_data["bandgap_ev"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "active_area_cm2":
                    norm_val, warn = normalize_area(val_str, unit_hint)
                    fields_data["active_area_cm2"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "aperture_area_cm2":
                    norm_val, warn = normalize_area(val_str, unit_hint)
                    fields_data["aperture_area_cm2"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "mask_area_cm2":
                    norm_val, warn = normalize_area(val_str, unit_hint)
                    fields_data["mask_area_cm2"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "stabilized_pce_percent":
                    norm_val, warn = normalize_pce(val_str, unit_hint)
                    fields_data["stabilized_pce_percent"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "reverse_scan_pce_percent":
                    norm_val, warn = normalize_pce(val_str, unit_hint)
                    fields_data["reverse_scan_pce_percent"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "forward_scan_pce_percent":
                    norm_val, warn = normalize_pce(val_str, unit_hint)
                    fields_data["forward_scan_pce_percent"] = norm_val
                    fields_data["warnings"].extend(warn)
                elif canonical == "scan_rate":
                    fields_data["scan_rate"] = to_float(val_str)
                elif canonical == "t80_h":
                    fields_data["t80_h"] = to_float(val_str)
                elif canonical == "temperature_c":
                    fields_data["temperature_c"] = to_float(val_str)
                elif canonical == "humidity_percent":
                    fields_data["humidity_percent"] = to_float(val_str)
                elif canonical == "mpp_tracking":
                    fields_data["mpp_tracking"] = str(val_str).strip()
                elif canonical == "encapsulation":
                    fields_data["encapsulation"] = str(val_str).strip()
                elif canonical == "isos_protocol":
                    fields_data["isos_protocol"] = str(val_str).strip()
                elif canonical == "scan_direction":
                    fields_data["scan_direction"] = str(val_str).strip()

            if not fields_data.get("device_id"):
                fields_data["device_id"] = f"device-{row_num}"

            pv_row = PVMetricRow(
                row_id=fields_data["row_id"],
                source_file=fields_data["source_file"],
                table_id=fields_data["table_id"],
                sheet_name=fields_data["sheet_name"],
                row_index=fields_data["row_index"],
                device_id=fields_data.get("device_id"),
                sample_id=fields_data.get("sample_id"),
                condition_label=fields_data.get("condition_label"),
                architecture=fields_data.get("architecture"),
                absorber=fields_data.get("absorber"),
                bandgap_ev=fields_data.get("bandgap_ev"),
                voc_v=fields_data.get("voc_v"),
                jsc_ma_cm2=fields_data.get("jsc_ma_cm2"),
                ff=fields_data.get("ff"),
                ff_unit=fields_data.get("ff_unit"),
                pce_percent=fields_data.get("pce_percent"),
                eqe_jsc_ma_cm2=fields_data.get("eqe_jsc_ma_cm2"),
                stabilized_pce_percent=fields_data.get("stabilized_pce_percent"),
                stabilized_power_output_percent=fields_data.get("stabilized_power_output_percent"),
                reverse_scan_pce_percent=fields_data.get("reverse_scan_pce_percent"),
                forward_scan_pce_percent=fields_data.get("forward_scan_pce_percent"),
                scan_direction=fields_data.get("scan_direction"),
                scan_rate=fields_data.get("scan_rate"),
                active_area_cm2=fields_data.get("active_area_cm2"),
                aperture_area_cm2=fields_data.get("aperture_area_cm2"),
                mask_area_cm2=fields_data.get("mask_area_cm2"),
                area_basis=fields_data.get("area_basis"),
                light_intensity_mw_cm2=fields_data.get("light_intensity_mw_cm2"),
                temperature_c=fields_data.get("temperature_c"),
                humidity_percent=fields_data.get("humidity_percent"),
                encapsulation=fields_data.get("encapsulation"),
                mpp_tracking=fields_data.get("mpp_tracking"),
                stability_duration_h=fields_data.get("stability_duration_h"),
                t80_h=fields_data.get("t80_h"),
                isos_protocol=fields_data.get("isos_protocol"),
                raw_values=fields_data["raw_values"],
                warnings=fields_data["warnings"]
            )
            pv_rows.append(pv_row)

    return pv_rows

