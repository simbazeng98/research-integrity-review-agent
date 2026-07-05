from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnProfile:
    """Statistical and type information profile for a single table column."""
    column_name: str
    inferred_type: str  # 'integer', 'float', 'string', 'mixed'
    numeric_count: int
    missing_count: int
    unique_count: int
    decimal_places_observed: dict[int, int] = field(default_factory=dict)
    terminal_digits_observed: dict[int, int] = field(default_factory=dict)
    unit_hint: str | None = None
    precision_hint: float | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_name": self.column_name,
            "inferred_type": self.inferred_type,
            "numeric_count": self.numeric_count,
            "missing_count": self.missing_count,
            "unique_count": self.unique_count,
            "decimal_places_observed": self.decimal_places_observed,
            "terminal_digits_observed": self.terminal_digits_observed,
            "unit_hint": self.unit_hint,
            "precision_hint": self.precision_hint,
            "warnings": self.warnings,
        }


@dataclass
class TableManifestItem:
    """Represents a single table sheet or tabular structure extracted from a file."""
    table_id: str
    source_file: str
    relative_path: str
    source_format: str  # 'csv', 'tsv', 'xlsx_sheet', 'markdown_table'
    sheet_name: str | None
    row_count: int
    column_count: int
    columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id,
            "source_file": self.source_file,
            "relative_path": self.relative_path,
            "source_format": self.source_format,
            "sheet_name": self.sheet_name,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "warnings": self.warnings,
        }


@dataclass
class TablePackageManifest:
    """The manifest tracking all tabular items in a target package."""
    package_path: str
    tables: list[TableManifestItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_path": self.package_path,
            "tables": [t.to_dict() for t in self.tables],
        }


@dataclass
class TableEvidenceFinding:
    """Represents a candidate numeric risk signal finding detected in a table."""
    finding_id: str
    rule_id: str
    risk_level: str
    table_id: str
    source_file: str
    column_names: list[str]
    row_range: str
    safe_report_language: str
    alternative_explanations: list[str] = field(default_factory=list)
    false_positive_risks: list[str] = field(default_factory=list)
    manual_verification: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "risk_level": self.risk_level,
            "table_id": self.table_id,
            "source_file": self.source_file,
            "column_names": self.column_names,
            "row_range": self.row_range,
            "safe_report_language": self.safe_report_language,
            "alternative_explanations": self.alternative_explanations,
            "false_positive_risks": self.false_positive_risks,
            "manual_verification": self.manual_verification,
            "metadata": self.metadata,
        }
