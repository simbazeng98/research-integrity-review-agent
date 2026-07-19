from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.core.tables.column_profiler import profile_column
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


def _decimal_or_none(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


_PLAIN_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def _terminal_digit(value: Any) -> str | None:
    text = str(value).strip()
    if not _PLAIN_NUMBER.fullmatch(text) or _decimal_or_none(text) is None:
        return None
    digits = [char for char in text if char.isdigit()]
    return digits[-1] if digits else None


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

    declared_formulas = options.get("declared_formulas")
    formula = _mapping_entry(declared_formulas, field)
    if formula is not None:
        context["role"] = "declared_formula"
        context["declared_formula"] = formula

    if not context.get("role"):
        context["role"] = _header_role(field)
    context["role"] = _normalized_name(str(context["role"]))
    return context


def _column_profile(field: str, values: list[str], options: Mapping[str, Any]) -> Any:
    supplied = options.get("column_profiles")
    entry = _mapping_entry(supplied, field)
    if entry is not None:
        return entry
    if isinstance(supplied, list):
        for candidate in supplied:
            name = (
                candidate.get("column_name")
                if isinstance(candidate, Mapping)
                else getattr(candidate, "column_name", None)
            )
            if str(name).casefold() == field.casefold():
                return candidate
    return profile_column(field, values)


def _profile_value(profile: Any, key: str) -> Any:
    if isinstance(profile, Mapping):
        return profile.get(key)
    return getattr(profile, key, None)


class TerminalDigitDetector(BaseDetector):
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
            csv_path = csv_path / "toy_terminal_digit_anomaly.csv"
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

        source_label = _safe_source_label(csv_path)
        table_id = str(options.get("table_id") or csv_path.stem)
        minimum_sample_size = max(5, int(rule.minimum_sample_size or 5))
        results: list[RuleExecutionResult] = []

        for field_index, field in enumerate(columns):
            context = _column_context(field, options)
            role = str(context["role"])
            if role in EXCLUDED_ROLES:
                continue

            values = [
                str(row[field_index]) if field_index < len(row) else ""
                for row in rows
            ]
            digits = [
                digit
                for digit in (_terminal_digit(value) for value in values)
                if digit is not None
            ]
            if len(digits) < minimum_sample_size:
                continue

            digit, count = Counter(digits).most_common(1)[0]
            fraction = count / len(digits)
            if fraction < 0.8:
                continue

            profile = _column_profile(field, values, options)
            precision_hint = _profile_value(profile, "precision_hint")
            declared_resolution = (
                context.get("declared_resolution")
                or context.get("resolution")
                or context.get("rounding_increment")
            )
            sufficient_sample = len(digits) >= MEDIUM_SAMPLE_SIZE
            open_for_scoring = sufficient_sample and declared_resolution is None
            risk_level = "medium" if open_for_scoring else "low"
            record_type = "integrity_finding" if open_for_scoring else "context_question"
            finding_id = f"RR-TD-{len(results) + 1:03d}"
            correlation_group = f"{source_label}|{table_id}|numeric_pattern"
            location = f"column {field}; {count}/{len(digits)} terminal digits"

            results.append(
                RuleExecutionResult(
                    finding_id=finding_id,
                    rule_id=rule.rule_id,
                    risk_level=risk_level,
                    evidence_items=[
                        {
                            "source": source_label,
                            "location": location,
                            "observed_pattern": (
                                f"terminal digit {digit} appears in {fraction:.0%} of values"
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
                        "Instrument precision or a declared rounding policy may constrain terminal digits.",
                        "The values may be binned, normalized, or derived from a disclosed formula.",
                        "A small sample can show a concentrated terminal digit by chance.",
                    ],
                    missing_verification_materials=list(rule.manual_verification),
                    suggested_verification_questions=[
                        "Please provide raw measurements and the rounding or significant-figure policy.",
                        "Please clarify whether these values are instrument exports or derived values.",
                    ],
                    limitations=[
                        "Terminal-digit concentration alone does not establish data independence or intent.",
                        "Small samples and declared resolution are retained only as non-scoring context questions.",
                    ],
                    metadata={
                        "detector_mode": "deterministic_context_gated",
                        "record_type": record_type,
                        "dominant_digit": digit,
                        "dominant_fraction": fraction,
                        "sample_size": len(digits),
                        "minimum_sample_size": minimum_sample_size,
                        "medium_sample_size": MEDIUM_SAMPLE_SIZE,
                        "column_role": role,
                        "precision_hint": precision_hint,
                        "declared_resolution": declared_resolution,
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


def detect_terminal_digits(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return TerminalDigitDetector().detect(package_dir, rule, options)
