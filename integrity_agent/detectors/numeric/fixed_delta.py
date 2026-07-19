from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.detectors.base import BaseDetector


MEDIUM_SAMPLE_SIZE = 15
EXCLUDED_ROLES = {
    "identifier",
    "row_index",
    "declared_formula",
    "formula",
    "derived",
    "normalization",
    "normalized",
    "unit_conversion",
}
CORRELATION_NOTICE = (
    "Related numeric-pattern signals retain separate evidence and must not be "
    "treated as independent probability multipliers."
)
CONTEXT_QUESTION_LANGUAGE = (
    "Candidate fixed-delta context question: confirm that the columns are "
    "nominally independent measurements before integrity scoring."
)


def _decimal_or_none(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_source_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(_project_root()).as_posix()
    except (OSError, ValueError):
        return path.name


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _header_role(field: str) -> str:
    name = _normalized_name(field)
    tokens = set(name.split("_"))
    if (
        name in {"id", "index", "row", "row_index", "record_number", "row_number"}
        or name.endswith("_id")
        or name.startswith("id_")
        or {"row", "index"}.issubset(tokens)
    ):
        return "identifier"
    if "formula" in tokens:
        return "declared_formula"
    if tokens.intersection({"derived", "calculated", "computed", "recomputed"}):
        return "derived"
    if tokens.intersection({"normalized", "normalised", "normalization", "normalisation", "norm"}):
        return "normalization"
    return "unspecified"


def _mapping_entry(mapping: Any, field: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    if field in mapping:
        return mapping[field]
    target = field.casefold()
    for key, value in mapping.items():
        if str(key).casefold() == target:
            return value
    return None


def _column_context(field: str, options: Mapping[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in ("column_contexts", "field_contexts", "column_semantics"):
        entry = _mapping_entry(options.get(key), field)
        if isinstance(entry, Mapping):
            context.update(dict(entry))
        elif isinstance(entry, str):
            context["role"] = entry

    role_entry = _mapping_entry(options.get("column_roles"), field)
    if isinstance(role_entry, str):
        context["role"] = role_entry
    unit_entry = _mapping_entry(options.get("column_units"), field)
    if unit_entry is not None:
        context["unit"] = unit_entry

    list_roles = {
        "id_columns": "identifier",
        "identifier_columns": "identifier",
        "row_index_columns": "row_index",
        "formula_columns": "declared_formula",
        "declared_formula_columns": "declared_formula",
        "derived_columns": "derived",
        "normalization_columns": "normalization",
        "normalized_columns": "normalization",
        "unit_conversion_columns": "unit_conversion",
        "independent_measurement_columns": "independent_measurement",
    }
    for option_key, role in list_roles.items():
        values = options.get(option_key) or []
        if any(str(value).casefold() == field.casefold() for value in values):
            context["role"] = role

    formula = _mapping_entry(options.get("declared_formulas"), field)
    if formula is not None:
        context["role"] = "declared_formula"
        context["declared_formula"] = formula

    if not context.get("role"):
        context["role"] = _header_role(field)
    context["role"] = _normalized_name(str(context["role"]))
    return context


def _pair_set(value: Any) -> set[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    if not isinstance(value, (list, tuple, set)):
        return pairs
    for pair in value:
        if isinstance(pair, Mapping):
            columns = pair.get("columns") or pair.get("fields")
        else:
            columns = pair
        if isinstance(columns, (list, tuple, set)) and len(columns) == 2:
            pairs.add(frozenset(str(column).casefold() for column in columns))
    return pairs


def _pair_is_explicitly_independent(
    first: str,
    second: str,
    first_context: Mapping[str, Any],
    second_context: Mapping[str, Any],
    options: Mapping[str, Any],
) -> tuple[bool, str]:
    pair = frozenset({first.casefold(), second.casefold()})
    declared_pairs = set()
    for key in ("nominally_independent_pairs", "independent_measurement_pairs"):
        declared_pairs |= _pair_set(options.get(key))
    if pair in declared_pairs:
        return True, "explicit_independent_pair"

    first_independent = (
        first_context.get("role") == "independent_measurement"
        or first_context.get("nominally_independent") is True
        or first_context.get("independent") is True
    )
    second_independent = (
        second_context.get("role") == "independent_measurement"
        or second_context.get("nominally_independent") is True
        or second_context.get("independent") is True
    )
    if first_independent and second_independent:
        return True, "both_columns_declared_independent"
    return False, "independence_not_declared"


def _temperature_scale(field: str, context: Mapping[str, Any]) -> str | None:
    raw_unit = str(context.get("unit") or "").strip().casefold().replace("℃", "°c")
    if raw_unit in {"c", "°c", "degc", "celsius"}:
        return "c"
    if raw_unit in {"k", "kelvin"}:
        return "k"
    name = _normalized_name(field)
    tokens = name.split("_")
    if tokens and tokens[-1] in {"c", "celsius", "degc"} and "temperature" in tokens:
        return "c"
    if tokens and tokens[-1] in {"k", "kelvin"} and "temperature" in tokens:
        return "k"
    return None


def _is_disclosed_unit_conversion(
    first: str,
    second: str,
    first_context: Mapping[str, Any],
    second_context: Mapping[str, Any],
    delta: Decimal,
    options: Mapping[str, Any],
) -> bool:
    pair = frozenset({first.casefold(), second.casefold()})
    if pair in _pair_set(options.get("unit_conversion_pairs")):
        return True
    if (
        first_context.get("role") == "unit_conversion"
        or second_context.get("role") == "unit_conversion"
    ):
        return True
    scales = {
        _temperature_scale(first, first_context),
        _temperature_scale(second, second_context),
    }
    return scales == {"c", "k"} and abs(abs(delta) - Decimal("273.15")) <= Decimal("0.01")


class FixedDeltaDetector(BaseDetector):
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
        options = dict(options or {})
        csv_path = Path(package_dir)
        sheet_name = None

        if "manifest_item" in options:
            manifest_item = options["manifest_item"]
            csv_path = Path(manifest_item.relative_path)
            sheet_name = manifest_item.sheet_name
        elif "file_path" in options:
            csv_path = Path(options["file_path"])
            sheet_name = options.get("sheet_name")
        elif csv_path.is_dir():
            csv_path = csv_path / "toy_numeric_fixed_delta.csv"
            if not csv_path.exists():
                return []

        if not csv_path.is_absolute():
            csv_path = (Path.cwd() / csv_path).resolve()
        if not csv_path.exists():
            fallback = (
                Path.cwd() / "examples" / "toy_table_package" / csv_path.name
            ).resolve()
            if not fallback.exists():
                return []
            csv_path = fallback

        from integrity_agent.core.tables.table_reader import read_any_table

        rows, columns, _warnings = read_any_table(csv_path, sheet_name=sheet_name)
        if not rows or not columns:
            return []

        contexts = {field: _column_context(field, options) for field in columns}
        numeric_fields: list[tuple[str, int]] = []
        for field_index, field in enumerate(columns):
            role = str(contexts[field]["role"])
            if role in EXCLUDED_ROLES:
                continue
            values = [
                row[field_index] if field_index < len(row) else ""
                for row in rows
            ]
            if values and all(_decimal_or_none(value) is not None for value in values):
                numeric_fields.append((field, field_index))

        if len(numeric_fields) < 2:
            return []

        source_label = _safe_source_label(csv_path)
        table_id = str(options.get("table_id") or csv_path.stem)
        minimum_sample_size = max(3, int(rule.minimum_sample_size or 3))
        results: list[RuleExecutionResult] = []

        for first_position, (first, first_index) in enumerate(numeric_fields):
            for second, second_index in numeric_fields[first_position + 1 :]:
                deltas = [
                    _decimal_or_none(row[second_index]) - _decimal_or_none(row[first_index])  # type: ignore[operator]
                    for row in rows
                ]
                if len(deltas) < minimum_sample_size or len(set(deltas)) != 1:
                    continue

                delta = deltas[0]
                if _is_disclosed_unit_conversion(
                    first,
                    second,
                    contexts[first],
                    contexts[second],
                    delta,
                    options,
                ):
                    continue

                independent, semantic_basis = _pair_is_explicitly_independent(
                    first,
                    second,
                    contexts[first],
                    contexts[second],
                    options,
                )
                sufficient_sample = len(deltas) >= MEDIUM_SAMPLE_SIZE
                open_for_scoring = independent and sufficient_sample
                risk_level = "medium" if open_for_scoring else "low"
                record_type = "integrity_finding" if open_for_scoring else "context_question"
                safe_language = (
                    rule.safe_report_language
                    if open_for_scoring
                    else CONTEXT_QUESTION_LANGUAGE
                )
                finding_id = f"RR-FD-{len(results) + 1:03d}"
                correlation_group = f"{source_label}|{table_id}|numeric_pattern"

                results.append(
                    RuleExecutionResult(
                        finding_id=finding_id,
                        rule_id=rule.rule_id,
                        risk_level=risk_level,
                        evidence_items=[
                            {
                                "source": source_label,
                                "location": (
                                    f"columns {first} and {second}; rows 1-{len(rows)}"
                                ),
                                "observed_pattern": (
                                    f"{second} - {first} is consistently {delta}"
                                ),
                            }
                        ],
                        manual_verification={
                            "needed": True,
                            "requests": list(rule.manual_verification),
                        },
                        false_positive_risks=list(rule.false_positive_risks),
                        safe_report_language=safe_language,
                        alternative_explanations=[
                            "A disclosed formula may derive one column from the other.",
                            "A unit conversion or normalization step may explain the constant difference.",
                            "The columns may not represent nominally independent measurements.",
                            "A small sample can show an exact difference without supporting a scored signal.",
                        ],
                        missing_verification_materials=list(rule.manual_verification),
                        suggested_verification_questions=[
                            "Please provide raw table data and any formulas used to generate these columns.",
                            "Please document whether the columns are nominally independent measurements.",
                        ],
                        limitations=[
                            "The runtime checks constant differences only; it does not implement a ratio detector.",
                            "A fixed difference does not by itself establish data independence or intent.",
                        ],
                        metadata={
                            "detector_mode": "delta_only_context_gated",
                            "record_type": record_type,
                            "delta": str(delta),
                            "sample_size": len(deltas),
                            "minimum_sample_size": minimum_sample_size,
                            "medium_sample_size": MEDIUM_SAMPLE_SIZE,
                            "nominally_independent_measurements": independent,
                            "semantic_basis": semantic_basis,
                            "first_column_role": contexts[first]["role"],
                            "second_column_role": contexts[second]["role"],
                            "open_for_scoring": open_for_scoring,
                            "mrpi_eligible": open_for_scoring,
                            "method_family": "numeric_pattern",
                            "correlation_group": correlation_group,
                            "correlation_notice": CORRELATION_NOTICE,
                            "runtime_status": self.runtime_status,
                            "execution_mode": self.execution_mode,
                            "risk_ceiling": self.risk_ceiling,
                            "requires_network": self.requires_network,
                            "requires_private_data": self.requires_private_data,
                            "table_id": table_id,
                        },
                    )
                )

        return results


def detect_fixed_delta(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return FixedDeltaDetector().detect(package_dir, rule, options)
