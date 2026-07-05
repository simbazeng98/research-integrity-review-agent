from __future__ import annotations

from integrity_agent.core.tables.table_schema import (
    ColumnProfile,
    TableManifestItem,
    TablePackageManifest,
    TableEvidenceFinding,
)


def test_column_profile_schema():
    profile = ColumnProfile(
        column_name="voltage",
        inferred_type="float",
        numeric_count=10,
        missing_count=0,
        unique_count=8,
        decimal_places_observed={1: 8, 2: 2},
        terminal_digits_observed={0: 2, 5: 8},
        unit_hint="V",
        precision_hint=0.1,
        warnings=[]
    )
    
    d = profile.to_dict()
    assert d["column_name"] == "voltage"
    assert d["inferred_type"] == "float"
    assert d["numeric_count"] == 10
    assert d["unit_hint"] == "V"


def test_table_manifest_item_schema():
    item = TableManifestItem(
        table_id="tbl-001",
        source_file="toy.csv",
        relative_path="examples/toy.csv",
        source_format="csv",
        sheet_name=None,
        row_count=15,
        column_count=2,
        columns=["voltage", "current"],
        warnings=[]
    )
    
    d = item.to_dict()
    assert d["table_id"] == "tbl-001"
    assert d["source_format"] == "csv"
    assert d["row_count"] == 15
    assert d["columns"] == ["voltage", "current"]


def test_table_package_manifest_schema():
    item = TableManifestItem(
        table_id="tbl-001",
        source_file="toy.csv",
        relative_path="examples/toy.csv",
        source_format="csv",
        sheet_name=None,
        row_count=15,
        column_count=2,
        columns=["voltage", "current"],
        warnings=[]
    )
    manifest = TablePackageManifest(
        package_path="examples/toy_table_package",
        tables=[item]
    )
    
    d = manifest.to_dict()
    assert d["package_path"] == "examples/toy_table_package"
    assert len(d["tables"]) == 1
    assert d["tables"][0]["table_id"] == "tbl-001"


def test_table_evidence_finding_schema():
    finding = TableEvidenceFinding(
        finding_id="TBL-FIND-001",
        rule_id="numeric_terminal_digit_anomaly",
        risk_level="medium",
        table_id="tbl-001",
        source_file="toy.csv",
        column_names=["voltage"],
        row_range="1-15",
        safe_report_language="Candidate numeric terminal-digit risk signal.",
        alternative_explanations=["precision policies"],
        false_positive_risks=["small samples"],
        manual_verification=["raw dataset"],
        metadata={"threshold": 0.5}
    )
    
    d = finding.to_dict()
    assert d["finding_id"] == "TBL-FIND-001"
    assert d["rule_id"] == "numeric_terminal_digit_anomaly"
    assert d["column_names"] == ["voltage"]
    assert d["metadata"] == {"threshold": 0.5}
