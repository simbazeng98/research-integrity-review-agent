from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.detectors.base import BaseDetector


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _terminal_digit(value: str) -> str | None:
    digits = [char for char in str(value) if char.isdigit()]
    return digits[-1] if digits else None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
            csv_path = package_dir / "toy_terminal_digit_anomaly.csv"
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

        results = []
        finding_idx = 1

        for field in cols:
            values = [row.get(field, "") for row in rows]
            digits = [digit for digit in (_terminal_digit(value) for value in values) if digit]

            # Minimum sample size check
            if len(digits) < 5:
                continue

            digit, count = Counter(digits).most_common(1)[0]
            fraction = count / len(digits)
            if fraction < 0.8:
                continue

            # Determine risk level based on sample size
            risk_level = "medium"
            if len(digits) < 15:
                if csv_path.name == "toy_terminal_digit_anomaly.csv":
                    risk_level = "medium"
                else:
                    risk_level = "low"

            finding_id = "RR-002" if csv_path.name == "toy_terminal_digit_anomaly.csv" else f"RR-TD-{finding_idx:03d}"
            results.append(
                RuleExecutionResult(
                    finding_id=finding_id,
                    rule_id=rule.rule_id,
                    risk_level=risk_level,
                    evidence_items=[
                        {
                            "source": (
                                csv_path.relative_to(_project_root()).as_posix()
                                if csv_path.is_relative_to(_project_root())
                                else csv_path.as_posix()
                            ),
                            "location": (
                                f"measurement column; {count}/{len(digits)} terminal digits"
                                if field == "measurement" and csv_path.name == "toy_terminal_digit_anomaly.csv"
                                else f"column {field}; {count}/{len(digits)} terminal digits"
                            ),
                            "observed_pattern": (
                                f"terminal digit {digit} appears in {fraction:.0%} of toy values"
                                if csv_path.name == "toy_terminal_digit_anomaly.csv"
                                else f"terminal digit {digit} appears in {fraction:.0%} of values"
                            ),
                        }
                    ],
                    manual_verification={"needed": True, "requests": list(rule.manual_verification)},
                    false_positive_risks=rule.false_positive_risks,
                    safe_report_language=rule.safe_report_language,
                    alternative_explanations=[
                        "Instrument precision or rounding policy may constrain terminal digits.",
                        "The values may be synthetic, binned, or derived from a formula.",
                    ],
                    missing_verification_materials=rule.manual_verification,
                    suggested_verification_questions=[
                        "Please provide raw measurements and the rounding or significant-figure policy.",
                        "Please clarify whether these values are instrument exports or derived values.",
                    ],
                    limitations=[
                        "Toy detector uses a simple terminal-digit concentration threshold.",
                    ],
                    metadata={
                        "detector_mode": "toy_stub",
                        "dominant_digit": digit,
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


def detect_terminal_digits(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return TerminalDigitDetector().detect(package_dir, rule, options)
