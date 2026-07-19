from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from integrity_agent.core.safety import find_runtime_safety_issues


ClaimType: TypeAlias = Literal[
    "anneal_temperature",
    "concentration",
    "layer_order",
    "composition",
    "trpl_fit",
    "tpv_fit",
    "pce",
    "other",
]
SourceDocument: TypeAlias = Literal[
    "main",
    "si",
    "figure",
    "table",
    "source_data",
    "response",
    "correction",
]
ClaimValue: TypeAlias = str | int | float


_NUMERIC_CLAIM_TYPES = {
    "anneal_temperature",
    "concentration",
    "trpl_fit",
    "tpv_fit",
    "pce",
}

_TIME_UNITS: dict[str, tuple[str, Decimal]] = {
    "ps": ("ns", Decimal("0.001")),
    "ns": ("ns", Decimal("1")),
    "us": ("ns", Decimal("1000")),
    "µs": ("ns", Decimal("1000")),
    "microsecond": ("ns", Decimal("1000")),
    "microseconds": ("ns", Decimal("1000")),
    "ms": ("ns", Decimal("1000000")),
    "s": ("ns", Decimal("1000000000")),
    "sec": ("ns", Decimal("1000000000")),
    "second": ("ns", Decimal("1000000000")),
    "seconds": ("ns", Decimal("1000000000")),
}

_TEMPERATURE_UNITS = {
    "c": "degC",
    "°c": "degC",
    "degc": "degC",
    "celsius": "degC",
    "k": "K",
    "kelvin": "K",
}

_CONCENTRATION_UNITS: dict[str, tuple[str, Decimal]] = {
    "mg/ml": ("mg/mL", Decimal("1")),
    "g/l": ("mg/mL", Decimal("1")),
    "ug/ml": ("mg/mL", Decimal("0.001")),
    "µg/ml": ("mg/mL", Decimal("0.001")),
    "m": ("M", Decimal("1")),
    "mol/l": ("M", Decimal("1")),
    "mol l-1": ("M", Decimal("1")),
    "mm": ("M", Decimal("0.001")),
    "mmol/l": ("M", Decimal("0.001")),
    "um": ("M", Decimal("0.000001")),
    "µm": ("M", Decimal("0.000001")),
    "umol/l": ("M", Decimal("0.000001")),
    "µmol/l": ("M", Decimal("0.000001")),
    "wt%": ("wt%", Decimal("1")),
    "w/w%": ("wt%", Decimal("1")),
    "vol%": ("vol%", Decimal("1")),
    "v/v%": ("vol%", Decimal("1")),
}

_PCE_UNITS: dict[str, tuple[str, Decimal]] = {
    "%": ("%", Decimal("1")),
    "percent": ("%", Decimal("1")),
    "percentage": ("%", Decimal("1")),
    "fraction": ("%", Decimal("100")),
}

_UNITLESS_UNITS = {"-", "none", "unitless", "dimensionless", "n/a", "na"}

_OTHER_UNITS = {
    *_UNITLESS_UNITS,
    "%",
    "nm",
    "um",
    "µm",
    "mm",
    "cm",
    "m",
    "ev",
    "v",
    "mv",
    "ma/cm2",
    "a/m2",
    "h",
    "min",
    "s",
}


def _unit_key(unit: str) -> str:
    return " ".join(
        unit.strip()
        .replace("μ", "µ")
        .replace("℃", "°C")
        .replace("⁻", "-")
        .replace("²", "2")
        .split()
    ).lower()


def _as_decimal(value: ClaimValue, *, claim_type: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"value for {claim_type} must be numeric, not boolean")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"value for {claim_type} must be numeric") from exc


def _json_number(value: Decimal) -> float:
    return float(value)


def normalize_claim_value_and_unit(
    claim_type: ClaimType,
    value: ClaimValue,
    unit: str,
) -> tuple[ClaimValue, str]:
    """Return a deterministic comparison value/unit without altering source fields."""
    key = _unit_key(unit)

    if claim_type in {"trpl_fit", "tpv_fit"}:
        if key not in _TIME_UNITS:
            raise ValueError(f"unit {unit!r} is not a supported time unit for {claim_type}")
        canonical, factor = _TIME_UNITS[key]
        return _json_number(_as_decimal(value, claim_type=claim_type) * factor), canonical

    if claim_type == "anneal_temperature":
        if key not in _TEMPERATURE_UNITS:
            raise ValueError(f"unit {unit!r} is not a supported temperature unit")
        numeric = _as_decimal(value, claim_type=claim_type)
        canonical = _TEMPERATURE_UNITS[key]
        if canonical == "K":
            numeric -= Decimal("273.15")
        return _json_number(numeric), "degC"

    if claim_type == "concentration":
        if key not in _CONCENTRATION_UNITS:
            raise ValueError(f"unit {unit!r} is not a supported concentration unit")
        canonical, factor = _CONCENTRATION_UNITS[key]
        return _json_number(_as_decimal(value, claim_type=claim_type) * factor), canonical

    if claim_type == "pce":
        if key not in _PCE_UNITS:
            raise ValueError(f"unit {unit!r} is not a supported PCE unit")
        canonical, factor = _PCE_UNITS[key]
        return _json_number(_as_decimal(value, claim_type=claim_type) * factor), canonical

    if claim_type in {"layer_order", "composition"}:
        if key not in _UNITLESS_UNITS:
            raise ValueError(f"unit {unit!r} must be an explicit unitless marker for {claim_type}")
        return value, "dimensionless"

    if claim_type == "other":
        if key not in _OTHER_UNITS:
            raise ValueError(f"unit {unit!r} is not supported for claim_type=other")
        canonical = "dimensionless" if key in _UNITLESS_UNITS else key
        return value, canonical

    raise ValueError(f"unsupported claim_type: {claim_type}")


class AtomicClaim(BaseModel):
    """A reviewer-located atomic claim; never an automatic finding by itself."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claim_id: str = Field(min_length=1)
    claim_type: ClaimType
    value: ClaimValue
    unit: str = Field(min_length=1)
    device_variant: str = Field(min_length=1)
    sample_id: str | None
    measurement_context: str | None
    source_document: SourceDocument
    source_version: str = Field(min_length=1)
    location: str = Field(min_length=1)
    source_hash: str = Field(min_length=1)
    human_confirmed: bool

    @field_validator("claim_id", "device_variant", "source_version")
    @classmethod
    def normalize_identity_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("sample_id", "measurement_context")
    @classmethod
    def normalize_optional_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("location", "source_hash")
    @classmethod
    def require_exact_nonblank_source_field(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_unit_and_public_safety(self) -> AtomicClaim:
        normalize_claim_value_and_unit(self.claim_type, self.value, self.unit)
        issues = find_runtime_safety_issues(self.model_dump(mode="json"))
        if issues:
            raise ValueError("; ".join(issues))
        return self

    @property
    def normalized_value(self) -> ClaimValue:
        return normalize_claim_value_and_unit(self.claim_type, self.value, self.unit)[0]

    @property
    def normalized_unit(self) -> str:
        return normalize_claim_value_and_unit(self.claim_type, self.value, self.unit)[1]

    @property
    def comparison_key(self) -> tuple[str, str, str | None, str | None, str]:
        return (
            self.claim_type,
            self.device_variant,
            self.sample_id,
            self.measurement_context,
            self.source_version,
        )

    def comparison_key_dict(self) -> dict[str, str | None]:
        return {
            "claim_type": self.claim_type,
            "device_variant": self.device_variant,
            "sample_id": self.sample_id,
            "measurement_context": self.measurement_context,
            "source_version": self.source_version,
        }

    @property
    def has_complete_comparison_context(self) -> bool:
        return bool(self.device_variant and self.sample_id and self.measurement_context)

    @property
    def eligible_for_finding(self) -> bool:
        return self.human_confirmed

    @property
    def record_status(self) -> Literal["confirmed", "draft_candidate"]:
        return "confirmed" if self.human_confirmed else "draft_candidate"

    def to_record(self) -> dict[str, Any]:
        record = self.model_dump(mode="json")
        record.update(
            {
                "normalized_value": self.normalized_value,
                "normalized_unit": self.normalized_unit,
                "comparison_key": self.comparison_key_dict(),
                "record_status": self.record_status,
                "eligible_for_finding": self.eligible_for_finding,
            }
        )
        return record


DocumentClaim = AtomicClaim


def claim_json_schema() -> dict[str, Any]:
    return AtomicClaim.model_json_schema()
