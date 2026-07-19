from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _valid_record() -> dict[str, object]:
    return {
        "finding_id": "F001",
        "finding_category": "image",
        "type": "image_similarity",
        "title": "Candidate image similarity signal",
        "summary": "Two local toy panels need manual verification.",
        "risk": "medium",
        "risk_level": "medium",
        "needs_manual_review": True,
        "evidence": [
            {
                "source": "examples/toy_image_package/images/img_a.png",
                "location": "Fig. 1a vs Fig. 2b",
                "metadata": {"workflow": "toy_fixture"},
            }
        ],
        "manual_verification": {
            "needed": True,
            "requests": ["Check original source images before reporting."],
        },
        "false_positive_risks": ["Shared controls can be legitimate when disclosed."],
        "alternative_explanations": ["Panels may be intentionally reused with clear labels."],
        "limitations": ["Toy fixture only."],
        "provenance": {"workflow": "test", "rule_id": "image_perceptual_similarity_candidate"},
    }


def _run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "integrity_agent", "validate-ledger", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_ledger_cli_accepts_valid_jsonl(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(_valid_record(), ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 0, result.stderr
    assert "Ledger validation passed" in result.stdout
    assert "records=1" in result.stdout


def test_validate_ledger_cli_rejects_schema_errors(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    bad = _valid_record()
    bad.pop("manual_verification")
    ledger.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 2
    assert "schema" in result.stderr.lower()
    assert "line 1" in result.stderr.lower()


def test_validate_ledger_cli_blocks_forbidden_phrase(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    bad = _valid_record()
    bad["summary"] = "This generated report says fraud confirmed."
    ledger.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 2
    assert "forbidden phrase" in result.stderr.lower()
    assert "fraud confirmed" in result.stderr.lower()


def test_validate_ledger_cli_blocks_private_path_leak(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    bad = _valid_record()
    bad["evidence"] = [
        {
            "source": "C:" + "\\Users\\private-user\\paper.pdf",
            "location": "local source",
        }
    ]
    ledger.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 2
    assert "private path" in result.stderr.lower()
    assert "line 1" in result.stderr.lower()


def test_validate_ledger_cli_blocks_posix_private_path_leak(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    bad = _valid_record()
    bad["evidence"] = [
        {
            "source": "/" + "home/private-user/paper.pdf",
            "location": "local source",
        }
    ]
    ledger.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 2
    assert "private" in result.stderr.lower()
    assert "line 1" in result.stderr.lower()


def test_validate_ledger_cli_blocks_sensitive_auth_fields(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    bad = _valid_record()
    sensitive_key = "xsec_" + "token"
    bad["provenance"] = {
        "workflow": "synthetic-negative-fixture",
        sensitive_key: "synthetic-redacted-value",
    }
    ledger.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 2
    assert "sensitive" in result.stderr.lower() or "auth" in result.stderr.lower()
    assert "line 1" in result.stderr.lower()


def test_validate_ledger_cli_accepts_existing_image_candidate_shape(tmp_path):
    ledger = tmp_path / "legacy_image_candidate.jsonl"
    legacy = {
        "candidate_id": "IMG-SIM-001",
        "rule_id": "image_perceptual_similarity_candidate",
        "relative_path_a": "images/img_a.png",
        "relative_path_b": "images/img_c_brightness.png",
        "risk_level": "medium",
        "safe_report_language": "Candidate visual similarity signal requiring source image review.",
        "alternative_explanations": ["same acquisition field exported differently"],
        "false_positive_risks": ["threshold sensitivity"],
        "manual_verification": ["original unprocessed image files", "acquisition metadata"],
        "limitations": ["global layout similarity only"],
    }
    ledger.write_text(json.dumps(legacy, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 0, result.stderr
    assert "records=1" in result.stdout


def test_validate_ledger_cli_inherits_source_file_for_evidence_items(tmp_path):
    ledger = tmp_path / "pv_finding.jsonl"
    pv_record = {
        "finding_id": "PV-FIND-001",
        "rule_id": "pv_pce_consistency",
        "risk_level": "medium",
        "source_file": "toy_pv_metrics_inconsistent.csv",
        "table_id": "tbl-004",
        "row_index": 1,
        "evidence_items": [{"location": "Row 1", "message": "Reported PCE differs."}],
        "safe_report_language": "Candidate PV metric consistency signal requiring unit review.",
        "alternative_explanations": ["FF unit convention mismatch"],
        "manual_verification": ["raw J-V data", "spreadsheet formula"],
    }
    ledger.write_text(json.dumps(pv_record, ensure_ascii=False) + "\n", encoding="utf-8")

    result = _run_validate(ledger)

    assert result.returncode == 0, result.stderr
    assert "records=1" in result.stdout


def test_validate_ledger_cli_writes_json_schema(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    schema_path = tmp_path / "evidence_record_schema.json"
    ledger.write_text(json.dumps(_valid_record(), ensure_ascii=False) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "integrity_agent",
            "validate-ledger",
            str(ledger),
            "--schema-output",
            str(schema_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["title"] == "EvidenceRecord"
    assert "finding_id" in schema["properties"]
