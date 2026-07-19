from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class JVCurve:
    curve_id: str
    source_file: str
    voltage_v: list[float]
    current_density_ma_cm2: list[float]
    scan_direction: str = "unknown"  # forward, reverse, unknown
    device_id_guess: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "source_file": self.source_file,
            "voltage_v": self.voltage_v,
            "current_density_ma_cm2": self.current_density_ma_cm2,
            "scan_direction": self.scan_direction,
            "device_id_guess": self.device_id_guess,
            "warnings": self.warnings
        }

@dataclass
class JVMetrics:
    curve_id: str
    device_id: str
    voc_v: float | None = None
    jsc_ma_cm2: float | None = None
    ff: float | None = None
    pce_percent: float | None = None
    vmp_v: float | None = None
    jmp_ma_cm2: float | None = None
    pmp_mw_cm2: float | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "device_id": self.device_id,
            "voc_v": self.voc_v,
            "jsc_ma_cm2": self.jsc_ma_cm2,
            "ff": self.ff,
            "pce_percent": self.pce_percent,
            "vmp_v": self.vmp_v,
            "jmp_ma_cm2": self.jmp_ma_cm2,
            "pmp_mw_cm2": self.pmp_mw_cm2,
            "warnings": self.warnings
        }

@dataclass
class JVHysteresisPair:
    pair_id: str
    device_id: str
    forward_curve: JVCurve
    reverse_curve: JVCurve
    forward_metrics: JVMetrics
    reverse_metrics: JVMetrics
    hysteresis_index: float
    abs_delta_pce: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "device_id": self.device_id,
            "forward_curve_id": self.forward_curve.curve_id,
            "reverse_curve_id": self.reverse_curve.curve_id,
            "forward_pce": self.forward_metrics.pce_percent,
            "reverse_pce": self.reverse_metrics.pce_percent,
            "hysteresis_index": self.hysteresis_index,
            "abs_delta_pce": self.abs_delta_pce,
            "warnings": self.warnings
        }

@dataclass
class EQESpectrum:
    spectrum_id: str
    source_file: str
    wavelength_nm: list[float]
    eqe_fraction: list[float]
    device_id_guess: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spectrum_id": self.spectrum_id,
            "source_file": self.source_file,
            "wavelength_nm": self.wavelength_nm,
            "eqe_fraction": self.eqe_fraction,
            "device_id_guess": self.device_id_guess,
            "warnings": self.warnings
        }

@dataclass
class EQEIntegrationResult:
    spectrum_id: str
    device_id: str
    integrated_jsc_ma_cm2: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spectrum_id": self.spectrum_id,
            "device_id": self.device_id,
            "integrated_jsc_ma_cm2": self.integrated_jsc_ma_cm2,
            "warnings": self.warnings
        }

@dataclass
class ExcelFormulaAuditItem:
    audit_id: str
    source_file: str
    sheet_name: str
    cell_coordinate: str
    formula: str | None = None
    cached_value: Any = None
    cell_value: Any = None
    audit_type: str = "formula_cell"  # formula_cell, hardcoded_output, formula_value_mismatch, volatile_function, external_reference
    message: str = ""
    severity: str = "low"  # low, medium

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "source_file": self.source_file,
            "sheet_name": self.sheet_name,
            "cell_coordinate": self.cell_coordinate,
            "formula": self.formula,
            "cached_value": self.cached_value,
            "cell_value": self.cell_value,
            "audit_type": self.audit_type,
            "message": self.message,
            "severity": self.severity
        }

@dataclass
class RawPVConsistencyFinding:
    finding_id: str
    rule_id: str
    detector_id: str
    risk_level: str
    risk_ceiling: str = "medium"
    source_file: str = ""
    device_id: str | None = None
    observed_values: dict[str, Any] = field(default_factory=dict)
    recomputed_values: dict[str, Any] = field(default_factory=dict)
    tolerance: dict[str, Any] | None = None
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    safe_report_language: str = ""
    alternative_explanations: list[str] = field(default_factory=list)
    false_positive_risks: list[str] = field(default_factory=list)
    manual_verification: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "detector_id": self.detector_id,
            "risk_level": self.risk_level,
            "risk_ceiling": self.risk_ceiling,
            "source_file": self.source_file,
            "device_id": self.device_id,
            "observed_values": self.observed_values,
            "recomputed_values": self.recomputed_values,
            "tolerance": self.tolerance,
            "evidence_items": self.evidence_items,
            "safe_report_language": self.safe_report_language,
            "alternative_explanations": self.alternative_explanations,
            "false_positive_risks": self.false_positive_risks,
            "manual_verification": self.manual_verification,
            "limitations": self.limitations,
            "metadata": self.metadata
        }
