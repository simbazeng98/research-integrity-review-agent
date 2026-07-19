from __future__ import annotations

import json
import os
import re
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import integrity_agent.__main__ as cli
import integrity_agent.workflows.review_package as review_package
import integrity_agent.workflows.report_viewer as report_viewer


def _directory_link_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"symlink creation is unavailable: {exc}")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            errors="replace",
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip(
                "symlink/junction creation is unavailable: "
                f"{result.stderr or result.stdout}"
            )


def _read_statuses(output_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (output_dir / "module_status.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def test_wizard_returns_nonzero_without_opening_failed_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    failed_summary = SimpleNamespace(
        overall_status="failed",
        module_statuses=[
            SimpleNamespace(
                module_name="report-reader-review",
                status="failed",
                error_message="synthetic report failure",
                skip_reason=None,
            )
        ],
    )
    monkeypatch.setattr(
        review_package,
        "run_review_package",
        lambda **_kwargs: failed_summary,
    )
    viewer_calls: list[object] = []
    monkeypatch.setattr(
        report_viewer,
        "start_server_and_open_browser",
        lambda *_args, **_kwargs: viewer_calls.append(object()),
    )

    result = cli.main(
        [
            "wizard",
            "--package-dir",
            str(package_dir),
            "--output-dir",
            str(tmp_path / "output"),
            "--view",
        ]
    )

    assert result != 0
    assert viewer_calls == []
    assert "report-reader-review" in capsys.readouterr().err


def test_reused_output_does_not_consume_stale_rules_or_keep_stale_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "unrelated-user-note.txt").write_text("KEEP", encoding="utf-8")
    (output_dir / "rule_findings.jsonl").write_text(
        json.dumps(
            {
                "finding_id": "STALE-001",
                "rule_id": "stale_rule",
                "risk_level": "medium",
                "safe_report_language": "STALE_MARKER",
                "source_file": "stale.csv",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    stale_summary = output_dir / "review_package_summary.md"
    stale_summary.write_text("STALE_SUMMARY", encoding="utf-8")

    def fail_report(*_args, **_kwargs):
        raise RuntimeError("synthetic report failure")

    monkeypatch.setattr(review_package, "write_reader_review_report", fail_report)
    summary = review_package.run_review_package(
        str(package_dir),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
        output_dir=str(output_dir),
    )

    assert summary.overall_status == "failed"
    assert "STALE_MARKER" not in (
        output_dir / "unified_evidence_index.jsonl"
    ).read_text(encoding="utf-8")
    assert not (output_dir / "rule_findings.jsonl").exists()
    assert not stale_summary.exists()
    assert (output_dir / "unrelated-user-note.txt").read_text(encoding="utf-8") == "KEEP"


def test_absolute_run_paths_and_tracebacks_are_not_persisted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "private-workspace" / "package"
    metadata_dir = package_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    doi_file = metadata_dir / "doi.txt"
    doi_file.write_text("10.1002/adma.202000000\n", encoding="utf-8")
    output_dir = tmp_path / "private-output"

    def fail_reader_intake(*_args, **_kwargs):
        raise RuntimeError(f"failed to read {doi_file}")

    monkeypatch.setattr(review_package, "run_reader_intake", fail_reader_intake)
    summary = review_package.run_review_package(
        str(package_dir.resolve()),
        skip_images=True,
        skip_tables=True,
        skip_pv=True,
        skip_raw_pv=True,
        output_dir=str(output_dir.resolve()),
    )

    assert summary.overall_status == "failed"
    persisted = []
    for path in output_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {
            ".json",
            ".jsonl",
            ".md",
            ".html",
            ".csv",
            ".tsv",
            ".txt",
            ".yml",
            ".yaml",
        }:
            persisted.append(path.read_text(encoding="utf-8", errors="ignore"))
    combined = "\n".join(persisted)
    assert str(tmp_path) not in combined
    assert "Traceback (most recent call last)" not in combined
    assert re.search(r"(?:[A-Za-z]:[\\/]|\\\\[^\\])", combined) is None

    manifest = json.loads(
        (output_dir / "review_package_manifest.json").read_text(encoding="utf-8")
    )
    inputs = manifest["manifest"]["inputs"]
    assert "documents_dir" in inputs
    assert all(not Path(value).is_absolute() for value in inputs.values())
    returned_inputs = summary.manifest.inputs.to_dict()
    assert returned_inputs == inputs
    assert summary.manifest.inputs.package_dir == "."
    assert all(not Path(value).is_absolute() for value in returned_inputs.values())

    reader_status = next(
        row for row in _read_statuses(output_dir) if row["module_name"] == "reader-intake"
    )
    assert reader_status["input_path"] == "metadata/doi.txt"
    assert reader_status["error_message"].startswith("RuntimeError:")


@pytest.mark.parametrize("output_relation", ["same", "ancestor", "descendant"])
def test_output_path_must_not_overlap_package_before_any_cleanup(
    tmp_path: Path,
    output_relation: str,
) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    marker = package_dir / "paper_case" / "source.txt"
    marker.parent.mkdir()
    marker.write_text("SOURCE", encoding="utf-8")
    if output_relation == "same":
        output_dir = package_dir
    elif output_relation == "ancestor":
        output_dir = tmp_path
    else:
        output_dir = package_dir / "generated"

    with pytest.raises(ValueError, match="overlap"):
        review_package.run_review_package(
            str(package_dir),
            skip_images=True,
            skip_tables=True,
            skip_pv=True,
            skip_raw_pv=True,
            output_dir=str(output_dir),
        )

    assert marker.read_text(encoding="utf-8") == "SOURCE"


def test_run_workspace_is_created_beside_output_on_same_volume(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    with review_package._same_volume_run_workspace(output_dir) as workspace:
        workspace_path = Path(workspace)
        assert workspace_path.parent == output_dir.parent.resolve()
        assert workspace_path.anchor.lower() == output_dir.resolve().anchor.lower()


def test_two_phase_publish_rolls_back_all_owned_artifacts_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_output = tmp_path / "output"
    staged_output = tmp_path / "transaction" / "staged"
    transaction_root = staged_output.parent
    final_output.mkdir()
    staged_output.mkdir(parents=True)
    (final_output / "review_package_summary.md").write_text("OLD", encoding="utf-8")
    (final_output / "review_package_manifest.json").write_text("OLD-MANIFEST", encoding="utf-8")
    (final_output / "unrelated.txt").write_text("KEEP", encoding="utf-8")
    (staged_output / "review_package_summary.md").write_text("NEW", encoding="utf-8")
    (staged_output / "review_package_manifest.json").write_text("NEW-MANIFEST", encoding="utf-8")

    real_move = review_package._move_path

    def fail_second_phase(source: Path, destination: Path) -> None:
        if source == staged_output / "review_package_manifest.json":
            raise OSError("synthetic publish failure")
        real_move(source, destination)

    monkeypatch.setattr(review_package, "_move_path", fail_second_phase)

    with pytest.raises(OSError, match="synthetic publish failure"):
        review_package._publish_owned_artifacts(
            staged_output,
            final_output,
            transaction_root,
        )

    assert (final_output / "review_package_summary.md").read_text(encoding="utf-8") == "OLD"
    assert (final_output / "review_package_manifest.json").read_text(encoding="utf-8") == "OLD-MANIFEST"
    assert (final_output / "unrelated.txt").read_text(encoding="utf-8") == "KEEP"


def test_staged_symlink_is_never_read_or_published(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    external_secret = external / "secret.json"
    external_secret.write_text('{"secret": "DO-NOT-TOUCH"}', encoding="utf-8")
    transaction_root = tmp_path / "transaction"
    staged_output = transaction_root / "staged"
    staged_output.mkdir(parents=True)
    link = staged_output / "paper_case"
    _directory_link_or_skip(link, external)

    with pytest.raises(RuntimeError, match="symlink"):
        review_package._sanitize_owned_artifacts(
            staged_output,
            (staged_output,),
        )
    with pytest.raises(RuntimeError, match="symlink"):
        review_package._publish_owned_artifacts(
            staged_output,
            tmp_path / "output",
            transaction_root,
        )

    assert external_secret.read_text(encoding="utf-8") == '{"secret": "DO-NOT-TOUCH"}'
    review_package._remove_path(link)
    assert not review_package._path_present(link)
    assert external_secret.read_text(encoding="utf-8") == '{"secret": "DO-NOT-TOUCH"}'


def test_publish_replaces_a_broken_owned_symlink(tmp_path: Path) -> None:
    final_output = tmp_path / "output"
    staged_output = tmp_path / "transaction" / "staged"
    transaction_root = staged_output.parent
    final_output.mkdir()
    staged_output.mkdir(parents=True)
    broken_link = final_output / "review_package_summary.md"
    old_target = tmp_path / "old-summary-target"
    old_target.mkdir()
    _directory_link_or_skip(broken_link, old_target)
    old_target.rmdir()
    assert review_package._path_present(broken_link) and not broken_link.exists()
    (staged_output / "review_package_summary.md").write_text(
        "NEW",
        encoding="utf-8",
    )

    review_package._publish_owned_artifacts(
        staged_output,
        final_output,
        transaction_root,
    )

    published = final_output / "review_package_summary.md"
    assert not published.is_symlink()
    assert published.read_text(encoding="utf-8") == "NEW"


def test_two_phase_publish_rolls_back_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_output = tmp_path / "output"
    staged_output = tmp_path / "transaction" / "staged"
    transaction_root = staged_output.parent
    final_output.mkdir()
    staged_output.mkdir(parents=True)
    (final_output / "review_package_summary.md").write_text("OLD", encoding="utf-8")
    (staged_output / "review_package_summary.md").write_text("NEW", encoding="utf-8")
    real_move = review_package._move_path

    def interrupt_publish(source: Path, destination: Path) -> None:
        if source == staged_output / "review_package_summary.md":
            raise KeyboardInterrupt()
        real_move(source, destination)

    monkeypatch.setattr(review_package, "_move_path", interrupt_publish)

    with pytest.raises(KeyboardInterrupt):
        review_package._publish_owned_artifacts(
            staged_output,
            final_output,
            transaction_root,
        )

    assert (final_output / "review_package_summary.md").read_text(encoding="utf-8") == "OLD"


@pytest.mark.parametrize(
    "private_path, forbidden_fragments",
    [
        (
            r'C:\Private User\Secret Folder\data file.csv',
            ("C:", "Private User", "Secret Folder", "data file.csv"),
        ),
        (
            r'\\server name\private share\secret file.txt',
            ("server name", "private share", "secret file.txt"),
        ),
    ],
)
def test_sanitizer_redacts_absolute_windows_and_unc_paths_with_spaces(
    tmp_path: Path,
    private_path: str,
    forbidden_fragments: tuple[str, ...],
) -> None:
    sanitized = review_package._sanitize_text(
        f'cannot open "{private_path}"',
        (tmp_path,),
    )

    assert "<local-path>" in sanitized
    assert all(fragment not in sanitized for fragment in forbidden_fragments)
    sanitized_mapping = review_package._sanitize_value(
        {private_path: "value"},
        (tmp_path,),
    )
    serialized_mapping = json.dumps(sanitized_mapping)
    assert all(
        fragment not in serialized_mapping
        for fragment in forbidden_fragments
    )


def test_sanitizer_fails_closed_for_malformed_owned_json(tmp_path: Path) -> None:
    staged_output = tmp_path / "transaction" / "staged"
    staged_output.mkdir(parents=True)
    malformed = staged_output / "review_package_manifest.json"
    malformed.write_text(
        '{"private_path": "C:\\Private Folder\\secret.json"',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="cannot safely sanitize"):
        review_package._sanitize_owned_artifacts(
            staged_output,
            (staged_output,),
        )


@pytest.mark.parametrize(
    ("suffix", "content", "message"),
    [
        (".json", '{"value":', "generated JSON artifact contains invalid JSON"),
        (
            ".jsonl",
            '{"valid": true}\n{not-json}\n',
            "generated JSONL artifact contains invalid JSON on line 2",
        ),
    ],
)
def test_safe_copy_rejects_malformed_structured_output_before_staging(
    tmp_path: Path,
    suffix: str,
    content: str,
    message: str,
) -> None:
    source = tmp_path / f"generated{suffix}"
    destination = tmp_path / "staged" / f"generated{suffix}"
    source.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        review_package.safe_copy_file(source, destination)

    assert not destination.exists()
