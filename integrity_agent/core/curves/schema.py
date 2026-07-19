from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from integrity_agent.core.safety import find_runtime_safety_issues


SUPPORTED_TABLE_SUFFIXES = {".csv", ".xlsx"}


class CurveInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: Decimal
    end: Decimal
    reason: str | None = None

    @model_validator(mode="after")
    def validate_order(self) -> CurveInterval:
        if self.start > self.end:
            raise ValueError("curve interval start must not exceed end")
        return self


class CurveDisclosure(BaseModel):
    """Author/publisher-supplied plotting context, never inferred as intent."""

    model_config = ConfigDict(extra="forbid")

    downsampling_disclosed: bool = False
    downsample_factor: int | None = Field(default=None, ge=2)
    axis_limits: tuple[Decimal, Decimal] | None = None
    filtering_disclosed: bool = False
    filtered_intervals: list[CurveInterval] = Field(default_factory=list)
    smoothing_disclosed: bool = False
    nan_omission_disclosed: bool = False
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_disclosure(self) -> CurveDisclosure:
        if self.downsample_factor is not None and not self.downsampling_disclosed:
            self.downsampling_disclosed = True
        if self.axis_limits is not None and self.axis_limits[0] > self.axis_limits[1]:
            raise ValueError("axis_limits minimum must not exceed maximum")
        issues = find_runtime_safety_issues(
            {
                "filtered_intervals": [
                    interval.model_dump(mode="json") for interval in self.filtered_intervals
                ],
                "notes": self.notes,
            }
        )
        if issues:
            raise ValueError("unsafe curve disclosure: " + "; ".join(issues))
        return self


class CurveTableSpec(BaseModel):
    """A supplied machine-readable table; image paths are deliberately rejected."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    source_label: str | None = None
    sheet_name: str | None = None
    location: str = Field(min_length=1)
    source_hash: str | None = None
    sample_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def require_machine_readable_table(cls, value: Path) -> Path:
        if value.suffix.lower() not in SUPPORTED_TABLE_SUFFIXES:
            raise ValueError(
                "curve reconciliation accepts supplied CSV/XLSX tables only; image digitization is not supported"
            )
        return value

    @field_validator("source_label", "sheet_name", "source_hash")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("sample_id", "source_version")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_public_trace_fields(self) -> CurveTableSpec:
        issues = find_runtime_safety_issues(
            {
                "source_label": self.source_label,
                "sheet_name": self.sheet_name,
                "location": self.location,
                "source_hash": self.source_hash,
                "sample_id": self.sample_id,
                "source_version": self.source_version,
            }
        )
        if issues:
            raise ValueError("unsafe curve traceability field: " + "; ".join(issues))
        return self

    @property
    def public_source(self) -> str:
        return self.source_label or self.path.name


class CurveColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_x: str = Field(min_length=1)
    source_y: str = Field(min_length=1)
    plot_x: str = Field(min_length=1)
    plot_y: str = Field(min_length=1)
    x_axis_kind: Literal["voltage", "time", "other"] = "other"
    x_tolerance: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_contiguous_missing: int = Field(default=2, ge=2)

    @field_validator("source_x", "source_y", "plot_x", "plot_y")
    @classmethod
    def normalize_column_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("column name must not be blank")
        return normalized


class CurveSegmentSimilarityOptions(BaseModel):
    """Explicit opt-in controls for comparing two independent numeric curves."""

    model_config = ConfigDict(extra="forbid")

    human_confirmed_independent_curves: bool = Field(strict=True)
    minimum_window_points: int = Field(default=8, ge=8)
    correlation_threshold: float = Field(default=0.999, ge=0.0, le=1.0)
    normalized_rmse_threshold: float = Field(default=0.01, gt=0.0, le=0.25)
    minimum_dynamic_range: float = Field(default=1e-6, gt=0.0)
    minimum_relative_dynamic_range: float = Field(default=1e-4, gt=0.0, le=1.0)
    near_linear_r2_threshold: float = Field(default=0.995, ge=0.0, le=1.0)
    sampling_correlation_threshold: float = Field(default=0.999, ge=0.0, le=1.0)
    sampling_normalized_rmse_threshold: float = Field(default=0.01, gt=0.0, le=0.25)
    maximum_points_per_curve: int = Field(default=500, ge=8)
    maximum_seed_candidates: int = Field(default=8, ge=1, le=1024)

    @model_validator(mode="after")
    def require_human_confirmation(self) -> CurveSegmentSimilarityOptions:
        if not self.human_confirmed_independent_curves:
            raise ValueError(
                "segment similarity requires human-confirmed independent curves"
            )
        if self.maximum_points_per_curve < self.minimum_window_points:
            raise ValueError(
                "maximum_points_per_curve must be at least minimum_window_points"
            )
        return self


class CurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: Decimal
    y: Decimal | None
    row_number: int = Field(ge=2)
    sequence_index: int = Field(ge=0)


class CurveReconciliationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_table: CurveTableSpec
    plot_table: CurveTableSpec
    mapping: CurveColumnMapping | None = None
    disclosure: CurveDisclosure = Field(default_factory=CurveDisclosure)
    segment_similarity: CurveSegmentSimilarityOptions | None = None

    @model_validator(mode="after")
    def require_segment_mapping(self) -> CurveReconciliationSpec:
        if self.segment_similarity is not None and self.mapping is None:
            raise ValueError(
                "segment similarity requires an explicit curve column mapping"
            )
        return self

    @property
    def context_matches(self) -> bool:
        return (
            self.source_table.sample_id == self.plot_table.sample_id
            and self.source_table.source_version == self.plot_table.source_version
        )


def curve_reconciliation_json_schema() -> dict[str, Any]:
    return CurveReconciliationSpec.model_json_schema()
