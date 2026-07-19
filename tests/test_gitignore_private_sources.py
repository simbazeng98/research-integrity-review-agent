from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _is_ignored(relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", relative_path],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode in {0, 1}, result.stderr
    return result.returncode == 0


def test_generic_private_source_root_is_ignored_as_a_complete_boundary():
    private_root = "private_sources"
    representative_private_files = [
        f"{private_root}/raw_json/user_profile.json",
        f"{private_root}/counter_sources/raw_json/image_manifest.json",
        f"{private_root}/source_papers/paper.pdf",
        f"{private_root}/source_data/device_metrics.xlsx",
        f"{private_root}/source_data/device_metrics.csv",
        f"{private_root}/images/account_avatar.jpg",
        f"{private_root}/independent_review/private_notes.txt",
    ]

    assert all(_is_ignored(path) for path in representative_private_files)


def test_examples_and_tests_do_not_reinclude_private_data_formats():
    sensitive_paths = [
        "examples/private_evidence.pdf",
        "examples/private_evidence.xlsx",
        "examples/private_evidence.csv",
        "examples/private_evidence.txt",
        "tests/private_evidence.pdf",
        "tests/private_evidence.xlsx",
        "tests/private_evidence.csv",
        "tests/private_evidence.txt",
    ]

    assert all(_is_ignored(path) for path in sensitive_paths)


def test_known_toy_fixtures_remain_explicitly_allowed():
    tracked_toy_fixtures = [
        "examples/toy_batch_intake/toy_dois.csv",
        "examples/toy_batch_intake/toy_dois.txt",
        "examples/toy_pv_package/toy_pv_multisheet.xlsx",
        "examples/toy_raw_pv_package/excel/toy_sheet.xlsm",
        "examples/toy_review_package/metadata/doi.txt",
        "examples/toy_review_package/tables/toy_terminal_digit.tsv",
        "examples/toy_rule_package/toy_numeric_fixed_delta.csv",
        "examples/toy_table_package/toy_multisheet.xlsx",
    ]

    assert all(not _is_ignored(path) for path in tracked_toy_fixtures)
