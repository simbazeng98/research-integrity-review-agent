from __future__ import annotations

import json
import socket
from pathlib import Path

import yaml

from integrity_agent.__main__ import main
from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)
from integrity_agent.core.images.image_schema import ImageEvidenceFinding


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_image_evidence_finding_is_core_finding_compatible():
    finding = ImageEvidenceFinding(
        finding_id="IMG-DUP-001",
        rule_id="image_exact_duplicate_sha256",
        risk_level="medium",
        evidence_items=[{"relative_path": "figures/a.png", "image_id": "img-1"}],
        safe_report_language="Exact duplicate image files detected; verify expected reuse.",
        alternative_explanations=["Repeated control image"],
        manual_verification=["Original acquisition file"],
    )

    assert isinstance(finding, Finding)

    record = finding.to_ledger_record()
    assert record["finding_category"] == "image"
    assert record["rule_id"] == "image_exact_duplicate_sha256"
    assert record["risk_level"] == "medium"
    assert record["evidence"][0]["source"] == "figures/a.png"
    assert record["manual_verification"]["requests"] == ["Original acquisition file"]


def test_bilingual_rule_loader_preserves_english_compatibility(tmp_path):
    rule_path = tmp_path / "bilingual_rule.yml"
    rule_path.write_text(
        yaml.safe_dump(
            {
                "rule_id": "toy_bilingual_rule",
                "status": "active",
                "title": {"en": "Toy signal", "zh": "玩具风险信号"},
                "description": {"en": "Toy description", "zh": "玩具描述"},
                "input_required": ["source_table"],
                "fields_required": ["numeric_matrix"],
                "risk_signal": {"en": "candidate numeric pattern", "zh": "候选数值模式"},
                "manual_verification": [
                    {"en": "Check raw table", "zh": "检查原始表格"}
                ],
                "false_positive_risks": [
                    {"en": "Rounded values", "zh": "四舍五入后的数值"}
                ],
                "safe_report_language": {
                    "en": "Candidate signal requiring manual review.",
                    "zh": "需要人工复核的候选风险信号。",
                },
                "runtime_status": "active",
                "execution_mode": "offline",
                "toy_fixture": None,
                "detector_module": None,
                "detector_function": None,
                "requires_network": False,
                "requires_private_data": False,
                "risk_ceiling": "medium",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    from integrity_agent.core.rules.registry import load_rule_registry

    rule = load_rule_registry(tmp_path)["toy_bilingual_rule"]
    assert rule.title["zh"] == "玩具风险信号"
    assert rule.safe_report_language == "Candidate signal requiring manual review."
    assert rule.safe_report_language_for("zh") == "需要人工复核的候选风险信号。"
    assert rule.manual_verification_for("zh") == ["检查原始表格"]


def test_i18n_manager_loads_runtime_translations():
    from integrity_agent.core.i18n.manager import I18nManager

    manager = I18nManager()
    manager.set_locale("zh")
    assert "研究诚信" in manager.translate("wizard.title")
    manager.set_locale("en")
    assert "Research Integrity" in manager.translate("wizard.title")


def test_domain_router_scores_empty_domain_skeletons():
    from integrity_agent.domains.router import available_domain_plugins, route_table_columns

    plugins = available_domain_plugins()
    plugin_ids = {plugin.get_domain_id() for plugin in plugins}
    assert {
        "ai_ml",
        "biomedical",
        "chemistry",
        "clinical",
        "materials_characterization",
        "psychology_social_science",
    }.issubset(plugin_ids)

    matches = route_table_columns(["trial_id", "arm_name", "age_mean", "age_sd", "p_val"])
    assert matches[0].domain_id == "clinical"
    assert matches[0].matched_fields["trial_id"] == "trial_id"
    assert matches[0].score > 0


def test_calculate_mrpi_returns_clamped_percentage():
    from integrity_agent.core.risk_model.risk_calculator import calculate_mrpi

    findings = [
        Finding(
            finding_id="F-H",
            type="exact_duplicate",
            title={"en": "High signal", "zh": "高优先级信号"},
            risk=RiskLevel.HIGH,
            summary={"en": "Needs review", "zh": "需要复核"},
            evidence=[EvidenceItem(source="toy", location="Fig. 1")],
            manual_verification=ManualVerification(needed=True, requests=["raw image"]),
            provenance={"confidence": 0.5},
        ),
        Finding(
            finding_id="F-M",
            type="similarity",
            title="Medium signal",
            risk=RiskLevel.MEDIUM,
            summary="Needs review",
            evidence=[EvidenceItem(source="toy", location="Fig. 2")],
            manual_verification=ManualVerification(needed=True, requests=["raw image"]),
        ),
        Finding(
            finding_id="F-L",
            type="metadata_gap",
            title="Low signal",
            risk=RiskLevel.LOW,
            summary="Needs review",
            evidence=[EvidenceItem(source="toy", location="Table 1")],
            manual_verification=ManualVerification(needed=True, requests=["methods"]),
        ),
    ]

    assert calculate_mrpi(findings) == 37.5
    assert calculate_mrpi([findings[0]] * 10) == 100.0


def test_dashboard_writer_is_offline_and_bilingual(tmp_path):
    from integrity_agent.core.reporting.html_dashboard import write_dashboard_html

    output = tmp_path / "review_report.html"
    write_dashboard_html(
        [
            {
                "finding_id": "F001",
                "rule_id": "image_exact_duplicate_sha256",
                "risk_level": "medium",
                "safe_report_language": {
                    "en": "Candidate duplicate image signal requiring manual review.",
                    "zh": "需要人工复核的候选重复图像信号。",
                },
                "alternative_explanations": [
                    {"en": "Shared control may be disclosed.", "zh": "共享对照可能已披露。"}
                ],
                "manual_verification": [
                    {"en": "Check original files.", "zh": "检查原始文件。"}
                ],
            }
        ],
        output,
        locale="zh",
    )

    html = output.read_text(encoding="utf-8")
    assert "需要人工复核的候选重复图像信号。" in html
    assert "Candidate duplicate image signal requiring manual review." in html
    assert "http://" not in html
    assert "https://" not in html
    assert "data-default-locale=\"zh\"" in html


def test_report_viewer_opens_local_dashboard(monkeypatch, tmp_path):
    from integrity_agent.workflows.report_viewer import start_server_and_open_browser

    (tmp_path / "review_report.html").write_text("<h1>ok</h1>", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    viewer = start_server_and_open_browser(tmp_path, port=_free_port())
    try:
        assert opened == [viewer.url]
        assert viewer.url.endswith("/review_report.html")
        assert viewer.port > 0
    finally:
        viewer.shutdown()


def test_wizard_dry_run_supports_zh(capsys, tmp_path):
    result = main(["wizard", "--lang", "zh", "--package-dir", str(tmp_path), "--dry-run"])

    captured = capsys.readouterr()
    assert result == 0
    assert "研究诚信" in captured.out
    assert "将分析目录" in captured.out


def test_review_package_summary_and_dashboard_integration(tmp_path):
    from integrity_agent.workflows.review_package import run_review_package
    toy_package = Path("examples/toy_review_package")
    if not toy_package.exists():
        toy_package = Path(__file__).resolve().parents[1] / "examples" / "toy_review_package"

    out_dir = tmp_path / "outputs"
    run_review_package(
        package_dir=str(toy_package),
        output_dir=str(out_dir),
        locale="zh",
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
    )

    dashboard = out_dir / "review_package_dashboard.html"
    summary_md = out_dir / "review_package_summary.md"

    assert dashboard.exists()
    assert summary_md.exists()

    dashboard_html = dashboard.read_text(encoding="utf-8")
    assert "data-default-locale=\"zh\"" in dashboard_html

    summary_text = summary_md.read_text(encoding="utf-8")
    assert "Interactive Review Dashboard" in summary_text
    assert "review_package_dashboard.html" in summary_text


def test_all_skeleton_domains_routing_and_findings(tmp_path):
    from integrity_agent.workflows.table_numeric_review import run_table_numeric_review

    # Create 6 dummy CSV tables matching the 6 disciplines
    columns_map = {
        "clinical": ["trial_id", "arm_name", "age_mean", "age_sd", "p_val"],
        "biomedical": ["gene_symbol", "expression_level", "band_intensity", "p_val", "sample_id"],
        "chemistry": ["peak_shift", "multiplicity", "coupling_constant", "element_percentage"],
        "materials_characterization": ["characterization_method", "instrument_model", "voltage", "pressure"],
        "ai_ml": ["model_name", "dataset_name", "metric", "reported_score"],
        "psychology_social_science": ["mean", "std_dev", "t_value", "f_value", "df", "sample_size"],
    }

    manifest_items = []
    for domain, cols in columns_map.items():
        csv_path = tmp_path / f"{domain}_table.csv"
        # Write CSV with headers and one row of dummy values
        csv_path.write_text(",".join(cols) + "\n" + ",".join(["1"] * len(cols)) + "\n", encoding="utf-8")

        manifest_items.append({
            "table_id": f"tbl_{domain}",
            "source_file": f"{domain}_table.csv",
            "relative_path": str(csv_path.resolve()),
            "source_format": "csv",
            "sheet_name": None,
            "row_count": 1,
            "column_count": len(cols),
            "columns": cols,
            "warnings": []
        })

    manifest_jsonl = tmp_path / "table_manifest.jsonl"
    with open(manifest_jsonl, "w", encoding="utf-8") as f:
        for item in manifest_items:
            f.write(json.dumps(item) + "\n")

    # Run the table numeric review
    output_dir = tmp_path / "outputs"
    findings_jsonl, summary_md = run_table_numeric_review(
        manifest_jsonl_path=manifest_jsonl,
        output_dir=output_dir
    )

    assert findings_jsonl.exists()
    assert summary_md.exists()

    # Load findings
    findings = []
    with open(findings_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))

    # We expect at least the 6 domain routing findings (and maybe other rule findings if matched, though dummy data won't trigger terminal digit/fixed delta usually)
    routed_domains = set()
    for f in findings:
        if f["rule_id"].startswith("domain_routing_"):
            domain_id = f["metadata"]["domain_id"]
            routed_domains.add(domain_id)
            assert f["metadata"]["status"] == "routing_only"
            assert f["metadata"]["not_implemented"] is True
            assert "routing_only" in f["safe_report_language"]
            assert "not_implemented" in f["safe_report_language"]

    assert routed_domains == {
        "clinical",
        "biomedical",
        "chemistry",
        "materials_characterization",
        "ai_ml",
        "psychology_social_science",
    }
