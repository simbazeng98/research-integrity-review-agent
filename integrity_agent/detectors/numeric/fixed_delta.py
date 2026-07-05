from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.detectors.base import BaseDetector


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _decimal_or_none(value: str) -> Decimal | None:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
        csv_path = package_dir
        sheet_name = None

        if options and "manifest_item" in options:
            manifest_item = options["manifest_item"]
            csv_path = Path(manifest_item.relative_path)
            sheet_name = manifest_item.sheet_name
        elif options and "file_path" in options:
            csv_path = Path(options["file_path"])
            sheet_name = options.get("sheet_name")
        elif package_dir.is_dir():
            csv_path = package_dir / "toy_numeric_fixed_delta.csv"
            if not csv_path.exists():
                return []

        if not csv_path.is_absolute():
            csv_path = (Path.cwd() / csv_path).resolve()

        if not csv_path.exists():
            # Try searching in examples
            fallback = (Path.cwd() / "examples" / "toy_table_package" / csv_path.name).resolve()
            if fallback.exists():
                csv_path = fallback
            else:
                return []

        from integrity_agent.core.tables.table_reader import read_any_table
        rows_vals, cols, warnings = read_any_table(csv_path, sheet_name=sheet_name)
        if not rows_vals or not cols:
            return []

        # Convert to list of dicts
        rows = []
        for row_list in rows_vals:
            row_dict = {}
            for col_idx, col_name in enumerate(cols):
                row_dict[col_name] = row_list[col_idx] if col_idx < len(row_list) else ""
            rows.append(row_dict)

        numeric_fields = []
        for field in cols:
            if rows and all(_decimal_or_none(row.get(field, "")) is not None for row in rows):
                numeric_fields.append(field)

        if len(numeric_fields) < 2:
            return []

        results = []
        finding_idx = 1

        for i in range(len(numeric_fields)):
            for j in range(i + 1, len(numeric_fields)):
                first = numeric_fields[i]
                second = numeric_fields[j]

                deltas = [
                    _decimal_or_none(row[second]) - _decimal_or_none(row[first])  # type: ignore[operator]
                    for row in rows
                ]
                if len(set(deltas)) != 1 or len(deltas) < 3:
                    continue

                delta = str(deltas[0])
                finding_id = "RR-001" if csv_path.name == "toy_numeric_fixed_delta.csv" else f"RR-FD-{finding_idx:03d}"
                results.append(
                    RuleExecutionResult(
                        finding_id=finding_id,
                        rule_id=rule.rule_id,
                        risk_level="medium",
                        evidence_items=[
                            {
                                "source": (
                                    csv_path.relative_to(_project_root()).as_posix()
                                    if csv_path.is_relative_to(_project_root())
                                    else csv_path.as_posix()
                                ),
                                "location": f"columns {first} and {second}; rows 1-{len(rows)}",
                                "observed_pattern": f"{second} - {first} is always {delta}",
                            }
                        ],
                        manual_verification={"needed": True, "requests": list(rule.manual_verification)},
                        false_positive_risks=rule.false_positive_risks,
                        safe_report_language=rule.safe_report_language,
                        alternative_explanations=[
                            "The second column may be a disclosed derived value.",
                            "A unit conversion or normalization step may explain the constant offset.",
                        ] if csv_path.name == "toy_numeric_fixed_delta.csv" else [
                            "The second column may be a disclosed derived value.",
                            "A unit conversion or normalization step may explain the constant offset.",
                            "derived columns, unit conversion, normalization, or formula columns are common legitimate explanations for a constant offset.",
                        ],
                        missing_verification_materials=rule.manual_verification,
                        suggested_verification_questions=[
                            "Please provide the raw table and formulas used to generate these columns.",
                            "Please explain whether the columns are independent measurements or derived values.",
                        ],
                        limitations=[
                            "Toy detector checks only the first two numeric columns in a synthetic CSV.",
                        ],
                        metadata={
                            "detector_mode": "toy_stub",
                            "delta": delta,
                            "runtime_status": self.runtime_status,
                            "execution_mode": self.execution_mode,
                            "risk_ceiling": self.risk_ceiling,
                            "requires_network": self.requires_network,
                            "requires_private_data": self.requires_private_data,
                            "table_id": options.get("table_id") if options else "tbl-001",
                        },
                    )
                )
                finding_idx += 1

        return results


def detect_fixed_delta(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return FixedDeltaDetector().detect(package_dir, rule, options)
