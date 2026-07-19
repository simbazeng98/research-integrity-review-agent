from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.core.tables.column_profiler import profile_column
from integrity_agent.core.tables.table_schema import ColumnProfile
from integrity_agent.detectors.base import BaseDetector


# Generic data-quality gates. They are deliberately independent of any paper,
# post, journal, or named case.
MIN_SAMPLE_SIZE = 8
MEDIUM_SAMPLE_SIZE = 20
MIN_LATTICE_OVERLAP = 0.90
MAX_NORMALIZED_RESIDUAL = 0.02
MIN_STEP_TO_PRECISION_RATIO = 1.5

_AXIS_OR_IDENTIFIER_RE = re.compile(
    r"(?:^|[_\s(])(time|index|row|id|identifier|wavelength|resolution)(?:$|[_\s)])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class QuantizationGridMetrics:
    total_count: int
    unique_count: int
    unique_ratio: float
    modal_value: float | None
    modal_count: int
    modal_ratio: float
    run_lengths: list[int]
    max_run_length: int
    min_positive_step: float | None
    modal_step: float | None
    modal_step_count: int
    lattice_step: float | None
    lattice_residual: float | None
    lattice_overlap: float | None
    grid_overlap: float | None
    declared_resolution: float | None
    resolution_explains_grid: bool
    precision_hint: float | None
    step_to_precision_ratio: float | None
    candidate_risk: str | None
    normalization_declared: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "unique_count": self.unique_count,
            "unique_ratio": self.unique_ratio,
            "modal_value": self.modal_value,
            "modal_count": self.modal_count,
            "modal_ratio": self.modal_ratio,
            "run_lengths": list(self.run_lengths),
            "max_run_length": self.max_run_length,
            "min_positive_step": self.min_positive_step,
            "modal_step": self.modal_step,
            "modal_step_count": self.modal_step_count,
            "lattice_step": self.lattice_step,
            "lattice_residual": self.lattice_residual,
            "lattice_overlap": self.lattice_overlap,
            "grid_overlap": self.grid_overlap,
            "declared_resolution": self.declared_resolution,
            "resolution_explains_grid": self.resolution_explains_grid,
            "precision_hint": self.precision_hint,
            "step_to_precision_ratio": self.step_to_precision_ratio,
            "candidate_risk": self.candidate_risk,
            "normalization_declared": self.normalization_declared,
        }


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "nan", "null", "none"}:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _positive_decimal_or_none(value: Any) -> Decimal | None:
    parsed = _decimal_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _profile_precision(profile: ColumnProfile | Mapping[str, Any] | None) -> Decimal | None:
    if isinstance(profile, ColumnProfile):
        raw = profile.precision_hint
    elif isinstance(profile, Mapping):
        raw = profile.get("precision_hint")
    else:
        raw = None
    return _positive_decimal_or_none(raw)


def _run_lengths(values: Sequence[Decimal]) -> list[int]:
    if not values:
        return []
    lengths: list[int] = []
    current = values[0]
    length = 1
    for value in values[1:]:
        if value == current:
            length += 1
        else:
            lengths.append(length)
            current = value
            length = 1
    lengths.append(length)
    return lengths


def _alignment_metrics(
    values: Sequence[Decimal],
    step: Decimal,
    *,
    tolerance: Decimal,
) -> tuple[float, float]:
    origin = min(values)
    distances: list[Decimal] = []
    aligned = 0
    for value in values:
        units = (value - origin) / step
        nearest = units.to_integral_value()
        distance = abs(units - nearest) * step
        distances.append(distance)
        if distance <= tolerance:
            aligned += 1
    overlap = aligned / len(values)
    normalized_residual = float(sum(distances, Decimal("0")) / len(values) / step)
    return overlap, normalized_residual


def _candidate_lattice(
    values: Sequence[Decimal],
    unique_values: Sequence[Decimal],
    precision_hint: Decimal | None,
) -> tuple[Decimal | None, float | None, float | None, Decimal | None, Decimal | None, int]:
    positive_steps = [
        current - previous
        for previous, current in zip(unique_values, unique_values[1:])
        if current > previous
    ]
    if not positive_steps:
        return None, None, None, None, None, 0

    min_step = min(positive_steps)
    step_counts = Counter(positive_steps)
    modal_step, modal_step_count = step_counts.most_common(1)[0]
    candidates = sorted(set(positive_steps))
    if precision_hint is not None:
        candidates = [
            step
            for step in candidates
            if step / precision_hint >= Decimal(str(MIN_STEP_TO_PRECISION_RATIO))
        ]
    if not candidates:
        return None, None, None, min_step, modal_step, modal_step_count

    best: tuple[float, float, Decimal] | None = None
    for step in candidates:
        tolerance = max(
            (precision_hint or Decimal("0")) / Decimal("4"),
            step * Decimal("0.000001"),
            Decimal("1e-12"),
        )
        overlap, residual = _alignment_metrics(values, step, tolerance=tolerance)
        candidate = (overlap, -residual, step)
        if best is None or candidate > best:
            best = candidate

    assert best is not None
    overlap, negative_residual, step = best
    return step, overlap, -negative_residual, min_step, modal_step, modal_step_count


def _jaccard_overlap(
    values: Sequence[Decimal],
    comparison_values: Iterable[Any] | None,
) -> float | None:
    if comparison_values is None:
        return None
    comparison = {
        parsed
        for parsed in (_decimal_or_none(value) for value in comparison_values)
        if parsed is not None
    }
    primary = set(values)
    union = primary | comparison
    if not union:
        return None
    return len(primary & comparison) / len(union)


def _resolution_explains(step: Decimal | None, resolution: Decimal | None) -> bool:
    if step is None or resolution is None or step < resolution:
        return False
    ratio = step / resolution
    nearest = ratio.to_integral_value()
    if nearest < 1:
        return False
    return abs(ratio - nearest) <= Decimal("0.02")


def analyze_quantization_grid(
    values: Iterable[Any],
    *,
    profile: ColumnProfile | Mapping[str, Any] | None = None,
    declared_resolution: Any = None,
    comparison_values: Iterable[Any] | None = None,
    normalized: bool = False,
) -> QuantizationGridMetrics:
    """Compute deterministic lattice/repetition metrics without creating a verdict."""
    raw_values = list(values)
    parsed = [
        value
        for value in (_decimal_or_none(item) for item in raw_values)
        if value is not None
    ]
    total = len(parsed)
    unique_values = sorted(set(parsed))
    unique_count = len(unique_values)
    unique_ratio = unique_count / total if total else 0.0

    if profile is None:
        profile = profile_column("value", [str(item) for item in raw_values])
    precision = _profile_precision(profile)
    resolution = _positive_decimal_or_none(declared_resolution)

    counts = Counter(parsed)
    if counts:
        modal_decimal, modal_count = counts.most_common(1)[0]
        modal_value = float(modal_decimal)
    else:
        modal_value = None
        modal_count = 0
    modal_ratio = modal_count / total if total else 0.0
    run_lengths = _run_lengths(parsed)

    (
        lattice_step,
        lattice_overlap,
        lattice_residual,
        min_step,
        modal_step,
        modal_step_count,
    ) = _candidate_lattice(parsed, unique_values, precision) if parsed else (
        None,
        None,
        None,
        None,
        None,
        0,
    )

    step_to_precision = (
        float(lattice_step / precision)
        if lattice_step is not None and precision is not None
        else None
    )
    explained = _resolution_explains(lattice_step, resolution)
    grid_overlap = _jaccard_overlap(parsed, comparison_values)

    strong_lattice = bool(
        lattice_step is not None
        and lattice_overlap is not None
        and lattice_overlap >= MIN_LATTICE_OVERLAP
        and lattice_residual is not None
        and lattice_residual <= MAX_NORMALIZED_RESIDUAL
    )
    repetition_support = bool(
        unique_ratio <= 0.75
        or modal_ratio >= 0.15
        or (run_lengths and max(run_lengths) >= 2)
    )
    if total < MIN_SAMPLE_SIZE or not strong_lattice or not repetition_support or explained:
        risk = None
    elif normalized:
        risk = "low"
    elif total >= MEDIUM_SAMPLE_SIZE:
        risk = "medium"
    else:
        risk = "low"

    return QuantizationGridMetrics(
        total_count=total,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
        modal_value=modal_value,
        modal_count=modal_count,
        modal_ratio=modal_ratio,
        run_lengths=run_lengths,
        max_run_length=max(run_lengths, default=0),
        min_positive_step=float(min_step) if min_step is not None else None,
        modal_step=float(modal_step) if modal_step is not None else None,
        modal_step_count=modal_step_count,
        lattice_step=float(lattice_step) if lattice_step is not None else None,
        lattice_residual=lattice_residual,
        lattice_overlap=lattice_overlap,
        grid_overlap=grid_overlap,
        declared_resolution=float(resolution) if resolution is not None else None,
        resolution_explains_grid=explained,
        precision_hint=float(precision) if precision is not None else None,
        step_to_precision_ratio=step_to_precision,
        candidate_risk=risk,
        normalization_declared=normalized,
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_source_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(_project_root()).as_posix()
    except (OSError, ValueError):
        return path.name


def _resolve_input_path(
    package_dir: Path,
    rule: DetectorRule,
    options: Mapping[str, Any],
) -> Path | None:
    if options.get("file_path") is not None:
        candidate = Path(options["file_path"])
    elif options.get("manifest_item") is not None:
        candidate = Path(options["manifest_item"].relative_path)
        if not candidate.is_absolute():
            base = Path(options.get("table_base_dir") or package_dir)
            candidate = base / candidate
    elif package_dir.is_file():
        candidate = package_dir
    elif rule.toy_fixture:
        fixture_name = Path(rule.toy_fixture).name
        local = package_dir / fixture_name
        candidate = local if local.exists() else _project_root() / rule.toy_fixture
    else:
        return None
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve()
    return candidate if candidate.is_file() else None


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if path.suffix.lower() != ".csv":
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _profile_from_options(
    options: Mapping[str, Any],
    column: str,
    values: list[str],
) -> tuple[ColumnProfile | Mapping[str, Any], str]:
    profiles = options.get("profiles")
    if isinstance(profiles, Mapping) and column in profiles:
        return profiles[column], "provided"
    profile = options.get("profile") or options.get("column_profile")
    if isinstance(profile, ColumnProfile):
        return profile, "provided"
    if isinstance(profile, Mapping):
        if column in profile and isinstance(profile[column], (ColumnProfile, Mapping)):
            return profile[column], "provided"
        if "precision_hint" in profile:
            return profile, "provided"
    return profile_column(column, values), "computed"


def _option_for_column(options: Mapping[str, Any], key: str, column: str) -> Any:
    raw = options.get(key)
    if isinstance(raw, Mapping):
        return raw.get(column)
    return raw


def _declared_resolution_from_rows(
    rows: Sequence[Mapping[str, str]],
    fields: Sequence[str],
    column: str,
) -> Decimal | None:
    candidates = [
        field
        for field in fields
        if field.lower() in {"declared_resolution", "resolution", f"{column.lower()}_resolution"}
    ]
    for field in candidates:
        parsed = [
            value
            for value in (_positive_decimal_or_none(row.get(field)) for row in rows)
            if value is not None
        ]
        if parsed and len(set(parsed)) == 1:
            return parsed[0]
    return None


def _numeric_columns(
    rows: Sequence[Mapping[str, str]],
    fields: Sequence[str],
    options: Mapping[str, Any],
) -> list[str]:
    requested = options.get("value_column")
    if requested is not None:
        return [str(requested)] if str(requested) in fields else []
    columns: list[str] = []
    for field in fields:
        if _AXIS_OR_IDENTIFIER_RE.search(field):
            continue
        values = [str(row.get(field, "")) for row in rows]
        profile = profile_column(field, values)
        if profile.numeric_count >= MIN_SAMPLE_SIZE and profile.inferred_type in {"integer", "float"}:
            columns.append(field)
    return columns


def _risk_not_above_ceiling(risk: str, ceiling: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    ceiling = ceiling if ceiling in order else "medium"
    return risk if order.get(risk, 0) <= order[ceiling] else ceiling


class QuantizationGridDetector(BaseDetector):
    runtime_status = "active"
    execution_mode = "offline"
    risk_ceiling = "medium"
    requires_network = False
    requires_private_data = False

    def detect(
        self,
        package_dir: Path,
        rule: DetectorRule,
        options: dict[str, Any] | None = None,
    ) -> list[RuleExecutionResult]:
        options = options or {}
        csv_path = _resolve_input_path(Path(package_dir), rule, options)
        if csv_path is None:
            return []
        rows, fields = _read_csv_rows(csv_path)
        if not rows or not fields:
            return []

        results: list[RuleExecutionResult] = []
        for column in _numeric_columns(rows, fields, options):
            values = [str(row.get(column, "")) for row in rows]
            profile, profile_source = _profile_from_options(options, column, values)
            declared = _option_for_column(options, "declared_resolution", column)
            if declared is None:
                declared = _declared_resolution_from_rows(rows, fields, column)
            comparison_values = _option_for_column(options, "comparison_values", column)
            comparison_column = options.get("comparison_column")
            if comparison_values is None and comparison_column in fields:
                comparison_values = [str(row.get(str(comparison_column), "")) for row in rows]
            normalized = bool(
                _option_for_column(options, "normalized", column)
                or _option_for_column(options, "normalization_declared", column)
            )
            metrics = analyze_quantization_grid(
                values,
                profile=profile,
                declared_resolution=declared,
                comparison_values=comparison_values,
                normalized=normalized,
            )
            if metrics.candidate_risk is None:
                continue

            risk = _risk_not_above_ceiling(metrics.candidate_risk, rule.risk_ceiling)
            source_label = _safe_source_label(csv_path)
            digest = hashlib.sha256(f"{source_label}:{column}".encode()).hexdigest()[:10]
            metadata = metrics.to_dict()
            metadata.update(
                {
                    "column_name": column,
                    "table_id": options.get("table_id"),
                    "profile_source": profile_source,
                    "runtime_status": self.runtime_status,
                    "execution_mode": self.execution_mode,
                    "risk_ceiling": self.risk_ceiling,
                    "requires_network": self.requires_network,
                    "requires_private_data": self.requires_private_data,
                    "detector_mode": "deterministic_quantization_grid",
                }
            )
            results.append(
                RuleExecutionResult(
                    finding_id=f"QG-{digest}",
                    rule_id=rule.rule_id,
                    risk_level=risk,
                    evidence_items=[
                        {
                            "source": source_label,
                            "location": f"column {column}; rows 1-{metrics.total_count}",
                            "observed_pattern": (
                                f"candidate lattice step {metrics.lattice_step}; "
                                f"lattice overlap {metrics.lattice_overlap:.1%}; "
                                f"unique ratio {metrics.unique_ratio:.1%}"
                            ),
                        }
                    ],
                    manual_verification={
                        "needed": True,
                        "requests": list(rule.manual_verification),
                    },
                    false_positive_risks=list(rule.false_positive_risks),
                    safe_report_language=rule.safe_report_language,
                    alternative_explanations=[
                        "Instrument or software export resolution may create a legitimate value grid.",
                        "Rounding, normalization, binning, or smoothing may increase repeated values.",
                        "Shared preprocessing may align related curves on the same grid.",
                        "Missing grid levels can arise from ordinary sampling and filtering.",
                    ],
                    missing_verification_materials=list(rule.manual_verification),
                    suggested_verification_questions=[
                        "What acquisition or export resolution was declared for this column?",
                        "Were the values rounded, normalized, binned, smoothed, or derived?",
                        "Can the supplied source-data or raw export reproduce the reported grid?",
                    ],
                    limitations=[
                        "The detector evaluates supplied numeric source tables only and does not infer intent.",
                        "A candidate grid is not evidence of a cause without instrument and preprocessing context.",
                    ],
                    metadata=metadata,
                )
            )
        return results


def detect_quantization_grid(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return QuantizationGridDetector().detect(Path(package_dir), rule, options)


__all__ = [
    "QuantizationGridDetector",
    "QuantizationGridMetrics",
    "analyze_quantization_grid",
    "detect_quantization_grid",
]
