from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time

from integrity_agent.core.path_display import display_path
from integrity_agent.core.safety import redact_public_text
import sys

from integrity_agent.core.packages.package_schema import (
    ReviewPackageInput,
    EvidenceModuleStatus,
    ReviewPackageManifest,
    ReviewPackageRunSummary,
)
from integrity_agent.workflows.reader_intake import run_reader_intake
from integrity_agent.workflows.image_intake import run_image_intake
from integrity_agent.workflows.image_similarity import run_image_similarity
from integrity_agent.workflows.table_intake import run_table_intake
from integrity_agent.workflows.table_numeric_review import run_table_numeric_review
from integrity_agent.workflows.pv_domain_review import run_pv_domain_review
from integrity_agent.workflows.raw_pv_reconciliation import run_raw_pv_reconciliation
from integrity_agent.workflows.report_reader_review import write_reader_review_report
from integrity_agent.workflows.report_review_package_html import run_report_review_package_html

OWNED_OUTPUT_NAMES = (
    "paper_case",
    "status_enrich",
    "reference_scan",
    "document_claim_intake",
    "cross_document_review",
    "version_reconciliation",
    "pv_decay_fit_review",
    "curve_reconciliation",
    "materials_process_lineage",
    "image_intake",
    "table_intake",
    "pv_domain",
    "pv_ruleset_review",
    "raw_pv",
    "rule_findings.jsonl",
    "unified_evidence_index.jsonl",
    "review_package_summary.md",
    "review_package_dashboard.html",
    "review_package_manifest.json",
    "module_status.jsonl",
)
SANITIZED_TEXT_SUFFIXES = {
    ".md",
    ".html",
    ".csv",
    ".tsv",
    ".txt",
    ".yml",
    ".yaml",
}
WINDOWS_ABSOLUTE_PATH_WITH_SPACES_RE = re.compile(
    r"(?:\\\\\?\\)?[A-Za-z]:[\\/](?![\\/])[^\r\n\"'<>|]+"
)
UNC_PATH_WITH_SPACES_RE = re.compile(
    r"\\\\(?!\?\\)[^\\/\r\n\"'<>|]+[\\/][^\r\n\"'<>|]+"
)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_run_paths(package_dir: Path, output_dir: Path) -> None:
    package_root = package_dir.resolve()
    output_root = output_dir.resolve()
    if (
        package_root == output_root
        or _is_within(package_root, output_root)
        or _is_within(output_root, package_root)
    ):
        raise ValueError(
            "review package and output directory overlap; choose disjoint paths"
        )


def _same_volume_run_workspace(output_dir: Path):
    output_parent = output_dir.resolve().parent
    output_parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.integrity-run-",
            dir=output_parent,
        )
    )

    class _RunWorkspace:
        name = str(workspace)

        def __enter__(self):
            return self.name

        def __exit__(self, *_exc_info):
            self.cleanup()

        def cleanup(self) -> None:
            _remove_path(workspace)

    return _RunWorkspace()


def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _is_directory_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0))


def _remove_path(path: Path) -> None:
    if path.is_symlink():
        path.unlink(missing_ok=True)
    elif _is_link_like(path):
        if _is_directory_reparse_point(path):
            path.rmdir()
        else:
            path.unlink(missing_ok=True)
    elif path.is_dir():
        for child in path.iterdir():
            _remove_path(child)
        path.rmdir()
    elif path.exists():
        path.unlink()


def _path_present(path: Path) -> bool:
    return path.exists() or _is_link_like(path)


def _move_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)


def _iter_staged_files(artifact: Path, staged_root: Path):
    pending = [artifact]
    while pending:
        current = pending.pop()
        if not _path_present(current):
            continue
        if _is_link_like(current):
            raise RuntimeError(
                f"staged review-package artifacts must not contain symlinks: "
                f"{current.name}"
            )
        try:
            current.resolve().relative_to(staged_root)
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                "staged review-package artifact resolves outside staging root"
            ) from exc
        if current.is_dir():
            pending.extend(current.iterdir())
        elif current.is_file():
            yield current


def _publish_owned_artifacts(
    staged_output: Path,
    final_output: Path,
    transaction_root: Path,
) -> None:
    if _is_link_like(staged_output):
        raise RuntimeError("staged review-package output must not be a symlink")
    staged_root = staged_output.resolve()
    try:
        staged_root.relative_to(transaction_root.resolve())
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            "staged review-package output must remain inside its transaction root"
        ) from exc

    owned_names = set(OWNED_OUTPUT_NAMES)
    unknown = sorted(
        child.name for child in staged_output.iterdir() if child.name not in owned_names
    )
    if unknown:
        raise RuntimeError(
            "staged review-package output contains unowned artifacts: "
            + ", ".join(unknown)
        )
    for child in staged_output.iterdir():
        for _ in _iter_staged_files(child, staged_root):
            pass

    final_output.mkdir(parents=True, exist_ok=True)
    backup_root = transaction_root / "rollback"
    _remove_path(backup_root)
    backup_root.mkdir(parents=True)
    backed_up: list[str] = []
    published: list[str] = []
    try:
        # Phase 1: retain every old owned artifact as a same-volume rollback set.
        for name in OWNED_OUTPUT_NAMES:
            existing = final_output / name
            if _path_present(existing):
                _move_path(existing, backup_root / name)
                backed_up.append(name)

        # Phase 2: publish the complete new owned set.
        for name in OWNED_OUTPUT_NAMES:
            staged = staged_output / name
            if _path_present(staged):
                _move_path(staged, final_output / name)
                published.append(name)
    except BaseException as publish_error:
        rollback_errors: list[str] = []
        for name in reversed(published):
            try:
                _remove_path(final_output / name)
            except BaseException as exc:
                rollback_errors.append(f"remove {name}: {exc}")
        for name in reversed(backed_up):
            backup = backup_root / name
            if not _path_present(backup):
                continue
            try:
                _move_path(backup, final_output / name)
            except BaseException as exc:
                rollback_errors.append(f"restore {name}: {exc}")
        if rollback_errors:
            raise RuntimeError(
                "review-package publish failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            ) from publish_error
        raise
    else:
        _remove_path(backup_root)


def _sanitize_text(text: str, roots: tuple[Path, ...]) -> str:
    sanitized = str(text)
    changed = False
    root_values = sorted(
        {str(root.resolve()) for root in roots},
        key=len,
        reverse=True,
    )
    for raw_root in root_values:
        variants = {
            raw_root,
            raw_root.replace("\\", "/"),
            raw_root.replace("\\", "\\\\"),
        }
        for variant in sorted(variants, key=len, reverse=True):
            for separator in ("\\\\", "\\", "/"):
                prefix = variant + separator
                if prefix in sanitized:
                    sanitized = sanitized.replace(prefix, "")
                    changed = True
            if variant in sanitized:
                sanitized = sanitized.replace(variant, ".")
                changed = True
    if changed:
        sanitized = sanitized.replace("\\", "/")
    sanitized = WINDOWS_ABSOLUTE_PATH_WITH_SPACES_RE.sub(
        "<local-path>",
        sanitized,
    )
    sanitized = UNC_PATH_WITH_SPACES_RE.sub("<local-path>", sanitized)
    return redact_public_text(sanitized)


def _sanitize_value(value, roots: tuple[Path, ...]):
    if isinstance(value, str):
        return _sanitize_text(value, roots)
    if isinstance(value, list):
        return [_sanitize_value(item, roots) for item in value]
    if isinstance(value, dict):
        return {
            _sanitize_text(key, roots) if isinstance(key, str) else key: _sanitize_value(
                item,
                roots,
            )
            for key, item in value.items()
        }
    return value


def _sanitize_owned_artifacts(output_dir: Path, roots: tuple[Path, ...]) -> None:
    if _is_link_like(output_dir):
        raise RuntimeError("staged review-package output must not be a symlink")
    staged_root = output_dir.resolve()
    for name in OWNED_OUTPUT_NAMES:
        artifact = output_dir / name
        for path in _iter_staged_files(artifact, staged_root):
            suffix = path.suffix.lower()
            if suffix == ".json":
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        f"cannot safely sanitize staged artifact: {path.name}"
                    ) from exc
                path.write_text(
                    json.dumps(
                        _sanitize_value(data, roots),
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            elif suffix == ".jsonl":
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                    records = [
                        _sanitize_value(json.loads(line), roots)
                        for line in lines
                        if line.strip()
                    ]
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        f"cannot safely sanitize staged artifact: {path.name}"
                    ) from exc
                path.write_text(
                    "".join(
                        json.dumps(record, ensure_ascii=False) + "\n"
                        for record in records
                    ),
                    encoding="utf-8",
                )
            elif suffix in SANITIZED_TEXT_SUFFIXES:
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise RuntimeError(
                        f"cannot safely sanitize staged artifact: {path.name}"
                    ) from exc
                path.write_text(_sanitize_text(text, roots), encoding="utf-8")


def _format_error(exc: Exception, roots: tuple[Path, ...]) -> str:
    return _sanitize_text(f"{type(exc).__name__}: {exc}", roots)


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Run paper/package-level evidence review.")
    parser.add_argument("package_dir", help="Path to package directory (e.g. examples/toy_review_package).")
    parser.add_argument("--skip-images", action="store_true", help="Skip image intake and similarity modules.")
    parser.add_argument("--skip-tables", action="store_true", help="Skip table intake and numeric reviews.")
    parser.add_argument("--skip-pv", action="store_true", help="Skip PV domain review module.")
    parser.add_argument("--skip-raw-pv", action="store_true", help="Skip raw PV recalculation module.")
    parser.add_argument("--allow-network", action="store_true", help="Allow network requests for metadata checks.")
    parser.add_argument("-o", "--output-dir", default="outputs/review_package", help="Directory to write output files.")
    return parser.parse_args(args)

def _validate_structured_copy_source(src: Path) -> None:
    """Reject malformed generated JSON before it enters the staged output tree."""
    suffix = src.suffix.lower()
    if suffix not in {".json", ".jsonl"}:
        return
    try:
        text = src.read_text(encoding="utf-8")
        if suffix == ".json":
            json.loads(text)
            return
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "generated JSONL artifact contains invalid JSON "
                    f"on line {line_number}"
                ) from exc
    except UnicodeError as exc:
        raise ValueError(
            "generated structured artifact is not valid UTF-8"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("generated JSON artifact contains invalid JSON") from exc


def safe_copy_file(src: Path | str, dest: Path | str) -> None:
    src_p = Path(src)
    dest_p = Path(dest)
    if src_p.exists():
        _validate_structured_copy_source(src_p)
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dest_p)

_TABLE_INPUT_SUFFIXES = {".csv", ".tsv", ".xlsx", ".md"}


def _count_table_input_artifacts(input_dir: Path | str) -> int:
    input_path = Path(input_dir)
    if not input_path.exists():
        return 0
    return sum(
        1
        for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in _TABLE_INPUT_SUFFIXES
    )


def _manifest_parsed_row_count(manifest_path: Path | str) -> int:
    total = 0
    path = Path(manifest_path)
    if not path.exists():
        return total
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                total += int(json.loads(line).get("row_count", 0) or 0)
    return total


def _jsonl_record_count(path: Path | str) -> int:
    jsonl_path = Path(path)
    if not jsonl_path.exists():
        return 0
    with jsonl_path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _load_yaml_records(path: Path, key: str) -> list[dict]:
    import yaml

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get(key)
    if payload is None:
        return []
    if not isinstance(payload, list) or not all(
        isinstance(record, dict) for record in payload
    ):
        raise ValueError(f"{path.name} must contain a {key!r} list of mappings")
    return [dict(record) for record in payload]


def _package_relative_runtime_path(package_dir: Path, raw_path: object) -> Path:
    if not isinstance(raw_path, (str, os.PathLike)) or not str(raw_path).strip():
        raise ValueError("structured table path must be a non-empty package-relative path")
    supplied = Path(raw_path)
    if supplied.is_absolute():
        raise ValueError("structured table paths must be package-relative")
    package_root = package_dir.resolve()
    resolved = (package_root / supplied).resolve()
    try:
        resolved.relative_to(package_root)
    except ValueError as exc:
        raise ValueError("structured table path escapes the review package") from exc
    return resolved


def _relative_if_within(value: str | None, *roots: Path) -> str | None:
    if value is None:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        return redact_public_text(candidate.as_posix())
    for root in roots:
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
    return redact_public_text(value)


def _write_validated_ledger(path: Path, records: list[dict]) -> Path:
    from integrity_agent.workflows.validate_ledger import validate_ledger_file

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    validation = validate_ledger_file(temp_path)
    if not validation.ok:
        temp_path.unlink(missing_ok=True)
        details = "; ".join(issue.format() for issue in validation.issues)
        raise ValueError(f"generated ledger validation failed: {details}")
    temp_path.replace(path)
    return path

def run_review_package(
    package_dir: str,
    skip_images: bool = False,
    skip_tables: bool = False,
    skip_pv: bool = False,
    skip_raw_pv: bool = False,
    allow_network: bool = False,
    output_dir: str = "outputs/review_package",
    locale: str = "en",
) -> ReviewPackageRunSummary:
    start_time = time.time()

    pack_path = Path(package_dir).expanduser().resolve()
    if not pack_path.is_dir():
        raise FileNotFoundError(f"review package directory not found: {pack_path.name}")
    final_out_path = Path(output_dir).expanduser()
    if not final_out_path.is_absolute():
        final_out_path = Path.cwd() / final_out_path
    final_out_path = final_out_path.resolve()
    _validate_run_paths(pack_path, final_out_path)
    final_out_path.parent.mkdir(parents=True, exist_ok=True)

    package_id = pack_path.name
    runtime_input = ReviewPackageInput(
        package_dir=str(pack_path),
        metadata_dir=str(pack_path / "metadata"),
        images_dir=str(pack_path / "images"),
        tables_dir=str(pack_path / "tables"),
        pv_dir=str(pack_path / "pv"),
        raw_pv_dir=str(pack_path / "raw_pv"),
        references_dir=str(pack_path / "references"),
        documents_dir=str(pack_path / "documents"),
    )
    public_input = ReviewPackageInput(
        package_dir=".",
        metadata_dir="metadata",
        images_dir="images",
        tables_dir="tables",
        pv_dir="pv",
        raw_pv_dir="raw_pv",
        references_dir="references",
        documents_dir="documents",
    )

    manifest = ReviewPackageManifest(
        package_id=package_id,
        inputs=public_input,
        created_at=start_time
    )

    module_statuses: list[EvidenceModuleStatus] = []

    # Collect manifests and profiles for PV ruleset review
    pv_ruleset_manifests = []
    pv_ruleset_profiles = []
    cross_document_effective_findings: Path | None = None
    structured_finding_files: list[Path] = []

    # The staged output and intermediates share the output volume, which makes
    # the final two-phase rename/rollback transaction deterministic.
    temp_dir_obj = _same_volume_run_workspace(final_out_path)
    run_workspace = Path(temp_dir_obj.name)
    out_path = run_workspace / "staged"
    out_path.mkdir()
    temp_dir = run_workspace / "intermediate"
    temp_dir.mkdir()
    privacy_roots = (
        out_path,
        temp_dir,
        run_workspace,
        pack_path,
        final_out_path,
    )

    try:
        # 1. Metadata Intake
        doi_file = Path(runtime_input.metadata_dir) / "doi.txt"
        if doi_file.exists():
            # Reader Intake
            m_start = time.time()
            try:
                with open(doi_file, "r", encoding="utf-8") as f:
                    doi = f.read().strip()

                if doi:
                    meta_json, intake_md = run_reader_intake(
                        doi_input=doi,
                        allow_network=allow_network,
                        output_dir=temp_dir / "paper_case"
                    )

                    # Copy to output_dir
                    safe_copy_file(meta_json, out_path / "paper_case/metadata.json")
                    safe_copy_file(intake_md, out_path / "paper_case/intake_summary.md")

                    module_statuses.append(EvidenceModuleStatus(
                        module_name="reader-intake",
                        status="success",
                        input_path=str(doi_file),
                        output_paths=[
                            str(out_path / "paper_case/metadata.json"),
                            str(out_path / "paper_case/intake_summary.md")
                        ],
                        runtime_seconds=time.time() - m_start
                    ))
                else:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="reader-intake",
                        status="warning",
                        input_path=str(doi_file),
                        warnings=["Empty DOI file"],
                        runtime_seconds=time.time() - m_start
                    ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="reader-intake",
                    status="failed",
                    input_path=str(doi_file),
                    error_message=_format_error(e, privacy_roots),
                    runtime_seconds=time.time() - m_start
                ))

            # Status Enrichment
            se_start = time.time()
            try:
                from integrity_agent.workflows.status_enrich import run_status_enrich
                se_jsonl, se_summary = run_status_enrich(
                    input_path=doi_file,
                    allow_network=allow_network,
                    output_dir=temp_dir / "status_enrich"
                )

                safe_copy_file(se_jsonl, out_path / "status_enrich/status_items.jsonl")
                safe_copy_file(se_summary, out_path / "status_enrich/status_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="status-enrich",
                    status="success",
                    input_path=str(doi_file),
                    output_paths=[
                        str(out_path / "status_enrich/status_items.jsonl"),
                        str(out_path / "status_enrich/status_summary.md")
                    ],
                    runtime_seconds=time.time() - se_start
                ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="status-enrich",
                    status="failed",
                    input_path=str(doi_file),
                    error_message=_format_error(e, privacy_roots),
                    runtime_seconds=time.time() - se_start
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="reader-intake",
                status="skipped",
                warnings=["No metadata/doi.txt found"]
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="status-enrich",
                status="skipped",
                warnings=["No metadata/doi.txt found"]
            ))

        # 1c. References / Bibliography Scan
        ref_start = time.time()
        ref_dir = Path(runtime_input.references_dir)
        ref_txt = ref_dir / "references.txt"
        ref_jsonl = ref_dir / "references.jsonl"

        # Check if references exist
        ref_file = None
        if ref_txt.exists():
            ref_file = ref_txt
        elif ref_jsonl.exists():
            ref_file = ref_jsonl

        if ref_file:
            try:
                from integrity_agent.workflows.reference_scan import run_reference_scan
                ref_jsonl_out, ref_summary_out = run_reference_scan(
                    input_path=ref_file,
                    allow_network=allow_network,
                    output_dir=temp_dir / "reference_scan"
                )

                safe_copy_file(ref_jsonl_out, out_path / "reference_scan/reference_anomalies.jsonl")
                safe_copy_file(ref_summary_out, out_path / "reference_scan/reference_anomaly_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="reference-scan",
                    status="success",
                    input_path=str(ref_file),
                    output_paths=[
                        str(out_path / "reference_scan/reference_anomalies.jsonl"),
                        str(out_path / "reference_scan/reference_anomaly_summary.md")
                    ],
                    runtime_seconds=time.time() - ref_start
                ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="reference-scan",
                    status="failed",
                    input_path=str(ref_file),
                    error_message=_format_error(e, privacy_roots),
                    runtime_seconds=time.time() - ref_start
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="reference-scan",
                status="skipped",
                warnings=["No references/references.txt or references/references.jsonl found"]
            ))

        # 1d. Human-confirmed document claims and publication versions
        claims_start = time.time()
        documents_dir = Path(runtime_input.documents_dir)
        claims_path = documents_dir / "claims.jsonl"
        version_manifest_path = documents_dir / "version_manifest.yml"
        if not claims_path.exists():
            for module_name in (
                "document-claim-intake",
                "cross-document-review",
                "version-reconciliation",
            ):
                module_statuses.append(EvidenceModuleStatus(
                    module_name=module_name,
                    status="skipped",
                    input_artifact_count=0,
                    parsed_row_count=0,
                    finding_count=0,
                    skip_reason="no_input_artifacts",
                    runtime_seconds=time.time() - claims_start,
                ))
        else:
            try:
                from integrity_agent.workflows.document_claim_intake import (
                    run_document_claim_intake,
                )

                normalized_claims, intake_manifest = run_document_claim_intake(
                    claims_path,
                    output_dir=temp_dir / "document_claim_intake",
                )
                intake_payload = json.loads(
                    Path(intake_manifest).read_text(encoding="utf-8")
                )
                safe_copy_file(
                    normalized_claims,
                    out_path / "document_claim_intake/document_claims.jsonl",
                )
                safe_copy_file(
                    intake_manifest,
                    out_path / "document_claim_intake/document_claim_intake_manifest.json",
                )
                normalized_claim_count = _jsonl_record_count(normalized_claims)
                module_statuses.append(EvidenceModuleStatus(
                    module_name="document-claim-intake",
                    status=str(intake_payload.get("status", "success")),
                    input_path="documents/claims.jsonl",
                    output_paths=[
                        str(out_path / "document_claim_intake/document_claims.jsonl"),
                        str(out_path / "document_claim_intake/document_claim_intake_manifest.json"),
                    ],
                    warnings=list(intake_payload.get("warnings") or []),
                    runtime_seconds=time.time() - claims_start,
                    input_artifact_count=1,
                    parsed_row_count=normalized_claim_count,
                    finding_count=0,
                ))

                crossdoc_start = time.time()
                from integrity_agent.workflows.cross_document_review import (
                    run_cross_document_review,
                )

                crossdoc_findings, crossdoc_summary = run_cross_document_review(
                    normalized_claims,
                    output_dir=temp_dir / "cross_document_review",
                )
                safe_copy_file(
                    crossdoc_findings,
                    out_path / "cross_document_review/cross_document_findings.jsonl",
                )
                safe_copy_file(
                    crossdoc_summary,
                    out_path / "cross_document_review/cross_document_review_summary.md",
                )
                crossdoc_finding_count = _jsonl_record_count(crossdoc_findings)
                cross_document_effective_findings = Path(crossdoc_findings)
                module_statuses.append(EvidenceModuleStatus(
                    module_name="cross-document-review",
                    status="success",
                    input_path="documents/claims.jsonl",
                    output_paths=[
                        str(out_path / "cross_document_review/cross_document_findings.jsonl"),
                        str(out_path / "cross_document_review/cross_document_review_summary.md"),
                    ],
                    runtime_seconds=time.time() - crossdoc_start,
                    input_artifact_count=1,
                    parsed_row_count=normalized_claim_count,
                    finding_count=crossdoc_finding_count,
                ))

                version_start = time.time()
                if version_manifest_path.exists():
                    from integrity_agent.workflows.validate_ledger import validate_ledger_file
                    from integrity_agent.workflows.version_reconciliation import (
                        run_version_reconciliation,
                    )

                    crossdoc_records = []
                    with Path(crossdoc_findings).open(encoding="utf-8") as handle:
                        crossdoc_records = [
                            json.loads(line) for line in handle if line.strip()
                        ]
                    version_result = run_version_reconciliation(
                        version_manifest_path,
                        findings=crossdoc_records,
                    )
                    version_dir = temp_dir / "version_reconciliation"
                    version_dir.mkdir(parents=True, exist_ok=True)
                    reconciled_path = version_dir / "reconciled_findings.jsonl"
                    with reconciled_path.open("w", encoding="utf-8", newline="\n") as handle:
                        for record in version_result.reconciled_findings:
                            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    ledger_validation = validate_ledger_file(reconciled_path)
                    if not ledger_validation.ok:
                        details = "; ".join(
                            issue.format() for issue in ledger_validation.issues
                        )
                        raise ValueError(
                            f"version-reconciled ledger validation failed: {details}"
                        )
                    version_summary = version_dir / "version_reconciliation_summary.json"
                    version_summary.write_text(
                        json.dumps(
                            version_result.to_record(),
                            ensure_ascii=False,
                            indent=2,
                        ) + "\n",
                        encoding="utf-8",
                    )
                    safe_copy_file(
                        reconciled_path,
                        out_path / "version_reconciliation/reconciled_findings.jsonl",
                    )
                    safe_copy_file(
                        version_summary,
                        out_path / "version_reconciliation/version_reconciliation_summary.json",
                    )
                    cross_document_effective_findings = reconciled_path
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="version-reconciliation",
                        status="success",
                        input_path="documents/version_manifest.yml",
                        output_paths=[
                            str(out_path / "version_reconciliation/reconciled_findings.jsonl"),
                            str(out_path / "version_reconciliation/version_reconciliation_summary.json"),
                        ],
                        runtime_seconds=time.time() - version_start,
                        input_artifact_count=1,
                        parsed_row_count=len(crossdoc_records),
                        finding_count=len(version_result.reconciled_findings),
                    ))
                else:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="version-reconciliation",
                        status="skipped",
                        input_artifact_count=0,
                        parsed_row_count=crossdoc_finding_count,
                        finding_count=0,
                        skip_reason="no_version_manifest",
                        runtime_seconds=time.time() - version_start,
                    ))
            except Exception as exc:
                existing_modules = {status.module_name for status in module_statuses}
                if "document-claim-intake" not in existing_modules:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="document-claim-intake",
                        status="failed",
                        input_path="documents/claims.jsonl",
                        error_message=str(exc),
                        input_artifact_count=1,
                        skip_reason="processing_failed",
                        runtime_seconds=time.time() - claims_start,
                    ))
                if "cross-document-review" not in existing_modules:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="cross-document-review",
                        status="failed",
                        error_message="Parent document claim workflow failed: " + str(exc),
                        input_artifact_count=1,
                        skip_reason="parent_claim_workflow_failed",
                    ))
                if "version-reconciliation" not in existing_modules:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="version-reconciliation",
                        status="failed",
                        error_message="Parent cross-document workflow failed: " + str(exc),
                        input_artifact_count=int(version_manifest_path.exists()),
                        skip_reason="parent_cross_document_workflow_failed",
                    ))

        # 1e. Structured domain reconciliation sidecars
        decay_input = documents_dir / "decay_fit_records.jsonl"
        decay_start = time.time()
        if decay_input.exists():
            try:
                from integrity_agent.workflows.pv_domain_review import (
                    run_pv_decay_fit_review,
                )

                parsed_decay_records = _jsonl_record_count(decay_input)
                decay_findings, decay_summary = run_pv_decay_fit_review(
                    decay_input,
                    output_dir=temp_dir / "pv_decay_fit_review",
                )
                # Keep the child ledger in the aggregation set even when it is
                # malformed so the unified gate records the failure.  Validate
                # before copying it into the staged publication tree: a failed
                # run may publish diagnostics, but it must never publish an
                # invalid child artifact.
                decay_findings = Path(decay_findings)
                structured_finding_files.append(decay_findings)
                from integrity_agent.workflows.validate_ledger import (
                    validate_ledger_file,
                )

                decay_validation = validate_ledger_file(decay_findings)
                if not decay_validation.ok:
                    details = "; ".join(
                        issue.format() for issue in decay_validation.issues
                    )
                    raise ValueError(
                        f"generated decay ledger validation failed: {details}"
                    )
                decay_output = out_path / "pv_decay_fit_review/pv_decay_fit_findings.jsonl"
                safe_copy_file(decay_findings, decay_output)
                safe_copy_file(
                    decay_summary,
                    out_path / "pv_decay_fit_review/pv_decay_fit_summary.md",
                )
                decay_finding_count = decay_validation.records
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-decay-fit-review",
                    status="success" if parsed_decay_records else "warning",
                    input_path="documents/decay_fit_records.jsonl",
                    output_paths=[
                        str(decay_output),
                        str(out_path / "pv_decay_fit_review/pv_decay_fit_summary.md"),
                    ],
                    input_artifact_count=1,
                    parsed_row_count=parsed_decay_records,
                    finding_count=decay_finding_count,
                    skip_reason=None if parsed_decay_records else "no_parsed_records",
                    runtime_seconds=time.time() - decay_start,
                ))
            except Exception as exc:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-decay-fit-review",
                    status="failed",
                    input_path="documents/decay_fit_records.jsonl",
                    error_message=str(exc),
                    input_artifact_count=1,
                    parsed_row_count=0,
                    finding_count=0,
                    skip_reason="processing_failed",
                    runtime_seconds=time.time() - decay_start,
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-decay-fit-review",
                status="skipped",
                input_path="documents/decay_fit_records.jsonl",
                input_artifact_count=0,
                parsed_row_count=0,
                finding_count=0,
                skip_reason="no_input_artifacts",
                runtime_seconds=time.time() - decay_start,
            ))

        curve_input = documents_dir / "curve_reconciliations.yml"
        curve_start = time.time()
        if curve_input.exists():
            try:
                from integrity_agent.core.curves import CurveReconciliationSpec
                from integrity_agent.core.rules.registry import load_rule_registry
                from integrity_agent.workflows.curve_reconciliation import (
                    reconcile_curve_coverage,
                    reconcile_curve_segment_similarity,
                )

                curve_specs = _load_yaml_records(curve_input, "reconciliations")
                curve_registry = load_rule_registry(
                    Path(__file__).resolve().parents[2]
                    / "knowledge_base"
                    / "detector_rules"
                )
                curve_rule = curve_registry["curve_point_coverage"]
                segment_rule = curve_registry["curve_segment_shape_similarity"]
                curve_findings = []
                segment_findings = []
                coverage_spec_count = 0
                segment_spec_count = 0
                for raw_spec in curve_specs:
                    prepared = dict(raw_spec)
                    for table_key in ("source_table", "plot_table"):
                        raw_table = prepared.get(table_key)
                        if not isinstance(raw_table, dict):
                            raise ValueError(f"{table_key} must be a mapping")
                        table = dict(raw_table)
                        public_path = Path(str(table.get("path") or "")).as_posix()
                        table["path"] = str(
                            _package_relative_runtime_path(pack_path, table.get("path"))
                        )
                        table.setdefault("source_label", public_path)
                        prepared[table_key] = table
                    spec = CurveReconciliationSpec.model_validate(prepared)
                    coverage_spec_count += 1
                    curve_findings.extend(
                        reconcile_curve_coverage(spec, rule=curve_rule)
                    )
                    if spec.segment_similarity is not None:
                        segment_spec_count += 1
                        segment_findings.extend(
                            reconcile_curve_segment_similarity(spec, rule=segment_rule)
                        )
                curve_records = [
                    finding.to_ledger_record() for finding in curve_findings
                ]
                segment_records = [
                    finding.to_ledger_record() for finding in segment_findings
                ]
                curve_ledger = _write_validated_ledger(
                    temp_dir / "curve_reconciliation/curve_point_coverage.jsonl",
                    curve_records,
                )
                segment_ledger = _write_validated_ledger(
                    temp_dir / "curve_reconciliation/curve_segment_similarity.jsonl",
                    segment_records,
                )
                curve_summary = temp_dir / "curve_reconciliation/curve_source_reconciliation_summary.md"
                curve_summary.write_text(
                    "# Curve Source Reconciliation Summary\n\n"
                    f"- Point-coverage comparisons: {coverage_spec_count}\n"
                    f"- Low, non-scoring coverage questions: {len(curve_records)}\n"
                    f"- Segment-similarity comparisons: {segment_spec_count}\n"
                    f"- Segment-shape candidates requiring manual review: {len(segment_records)}\n"
                    "- Image digitization performed: no\n"
                    "- Do-not-overclaim: verify mapping and plotting context before interpretation.\n",
                    encoding="utf-8",
                )
                curve_output = out_path / "curve_reconciliation/curve_point_coverage.jsonl"
                segment_output = out_path / "curve_reconciliation/curve_segment_similarity.jsonl"
                safe_copy_file(curve_ledger, curve_output)
                safe_copy_file(segment_ledger, segment_output)
                safe_copy_file(
                    curve_summary,
                    out_path / "curve_reconciliation/curve_source_reconciliation_summary.md",
                )
                structured_finding_files.append(curve_ledger)
                structured_finding_files.append(segment_ledger)
                module_statuses.append(EvidenceModuleStatus(
                    module_name="curve-point-coverage",
                    status="success" if coverage_spec_count else "warning",
                    input_path="documents/curve_reconciliations.yml",
                    output_paths=[
                        str(curve_output),
                        str(out_path / "curve_reconciliation/curve_source_reconciliation_summary.md"),
                    ],
                    input_artifact_count=1,
                    parsed_row_count=coverage_spec_count,
                    finding_count=len(curve_records),
                    skip_reason=None if coverage_spec_count else "no_parsed_records",
                    warnings=(
                        []
                        if coverage_spec_count
                        else ["Curve reconciliation input contained no records."]
                    ),
                    runtime_seconds=time.time() - curve_start,
                ))
                module_statuses.append(EvidenceModuleStatus(
                    module_name="curve-segment-similarity",
                    status=(
                        "success"
                        if segment_spec_count
                        else "warning" if not coverage_spec_count else "skipped"
                    ),
                    input_path="documents/curve_reconciliations.yml",
                    output_paths=[str(segment_output)],
                    input_artifact_count=1,
                    parsed_row_count=segment_spec_count,
                    finding_count=len(segment_records),
                    skip_reason=(
                        None
                        if segment_spec_count
                        else "no_parsed_records"
                        if not coverage_spec_count
                        else "no_segment_similarity_specs"
                    ),
                    warnings=(
                        ["Curve reconciliation input contained no records."]
                        if not coverage_spec_count
                        else []
                    ),
                    runtime_seconds=time.time() - curve_start,
                ))
            except Exception as exc:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="curve-point-coverage",
                    status="failed",
                    input_path="documents/curve_reconciliations.yml",
                    error_message=str(exc),
                    input_artifact_count=1,
                    parsed_row_count=0,
                    finding_count=0,
                    skip_reason="processing_failed",
                    runtime_seconds=time.time() - curve_start,
                ))
                module_statuses.append(EvidenceModuleStatus(
                    module_name="curve-segment-similarity",
                    status="failed",
                    input_path="documents/curve_reconciliations.yml",
                    error_message=str(exc),
                    input_artifact_count=1,
                    parsed_row_count=0,
                    finding_count=0,
                    skip_reason="processing_failed",
                    runtime_seconds=time.time() - curve_start,
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="curve-point-coverage",
                status="skipped",
                input_path="documents/curve_reconciliations.yml",
                input_artifact_count=0,
                parsed_row_count=0,
                finding_count=0,
                skip_reason="no_input_artifacts",
                runtime_seconds=time.time() - curve_start,
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="curve-segment-similarity",
                status="skipped",
                input_path="documents/curve_reconciliations.yml",
                input_artifact_count=0,
                parsed_row_count=0,
                finding_count=0,
                skip_reason="no_input_artifacts",
                runtime_seconds=time.time() - curve_start,
            ))

        lineage_input = documents_dir / "materials_process_lineage.yml"
        lineage_start = time.time()
        if lineage_input.exists():
            try:
                from integrity_agent.domains.materials_characterization.process_lineage import (
                    run_materials_process_lineage_check,
                )

                lineage_records = _load_yaml_records(lineage_input, "records")
                lineage_findings = run_materials_process_lineage_check(
                    lineage_records
                )
                lineage_ledger_records = [
                    finding.model_dump(mode="json") for finding in lineage_findings
                ]
                lineage_ledger = _write_validated_ledger(
                    temp_dir
                    / "materials_process_lineage/materials_process_lineage_findings.jsonl",
                    lineage_ledger_records,
                )
                lineage_summary = temp_dir / "materials_process_lineage/materials_process_lineage_summary.md"
                lineage_summary.write_text(
                    "# Materials Process Lineage Summary\n\n"
                    f"- Structured records: {len(lineage_records)}\n"
                    f"- Low, non-scoring verification questions: {len(lineage_ledger_records)}\n"
                    "- Do-not-overclaim: sample-stage questions require manual context and do not establish intent.\n",
                    encoding="utf-8",
                )
                lineage_output = (
                    out_path
                    / "materials_process_lineage/materials_process_lineage_findings.jsonl"
                )
                safe_copy_file(lineage_ledger, lineage_output)
                safe_copy_file(
                    lineage_summary,
                    out_path / "materials_process_lineage/materials_process_lineage_summary.md",
                )
                structured_finding_files.append(lineage_ledger)
                module_statuses.append(EvidenceModuleStatus(
                    module_name="materials-process-lineage",
                    status="success" if lineage_records else "warning",
                    input_path="documents/materials_process_lineage.yml",
                    output_paths=[
                        str(lineage_output),
                        str(out_path / "materials_process_lineage/materials_process_lineage_summary.md"),
                    ],
                    input_artifact_count=1,
                    parsed_row_count=len(lineage_records),
                    finding_count=len(lineage_ledger_records),
                    skip_reason=None if lineage_records else "no_parsed_records",
                    runtime_seconds=time.time() - lineage_start,
                ))
            except Exception as exc:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="materials-process-lineage",
                    status="failed",
                    input_path="documents/materials_process_lineage.yml",
                    error_message=str(exc),
                    input_artifact_count=1,
                    parsed_row_count=0,
                    finding_count=0,
                    skip_reason="processing_failed",
                    runtime_seconds=time.time() - lineage_start,
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="materials-process-lineage",
                status="skipped",
                input_path="documents/materials_process_lineage.yml",
                input_artifact_count=0,
                parsed_row_count=0,
                finding_count=0,
                skip_reason="no_input_artifacts",
                runtime_seconds=time.time() - lineage_start,
            ))

        # 2. Image Intake & Similarity
        if skip_images or not Path(runtime_input.images_dir).exists():
            module_statuses.append(EvidenceModuleStatus(
                module_name="image-intake",
                status="skipped",
                warnings=["Skipped by configuration or missing folder"]
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="image-similarity",
                status="skipped",
                warnings=["Skipped by configuration or missing folder"]
            ))
        else:
            # Image Intake
            m_start = time.time()
            try:
                manifest_jsonl, manifest_csv, findings_jsonl, summary_md = run_image_intake(
                    folder_path=runtime_input.images_dir,
                    output_dir=temp_dir / "image_intake"
                )

                safe_copy_file(manifest_jsonl, out_path / "image_intake/image_manifest.jsonl")
                safe_copy_file(manifest_csv, out_path / "image_intake/image_manifest.csv")
                safe_copy_file(findings_jsonl, out_path / "image_intake/image_findings.jsonl")
                safe_copy_file(summary_md, out_path / "image_intake/image_intake_summary.md")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="image-intake",
                    status="success",
                    input_path=runtime_input.images_dir,
                    output_paths=[
                        str(out_path / "image_intake/image_manifest.jsonl"),
                        str(out_path / "image_intake/image_findings.jsonl")
                    ],
                    runtime_seconds=time.time() - m_start
                ))

                # Image Similarity
                sim_start = time.time()
                try:
                    hashes_jsonl, candidates_jsonl, sim_summary_md = run_image_similarity(
                        manifest_jsonl_path=temp_dir / "image_intake/image_manifest.jsonl",
                        output_dir=temp_dir / "image_intake",
                        threshold=6,
                        hash_method="dhash"
                    )

                    safe_copy_file(hashes_jsonl, out_path / "image_intake/image_hashes.jsonl")
                    safe_copy_file(candidates_jsonl, out_path / "image_intake/image_similarity_candidates.jsonl")
                    safe_copy_file(sim_summary_md, out_path / "image_intake/image_similarity_summary.md")

                    module_statuses.append(EvidenceModuleStatus(
                        module_name="image-similarity",
                        status="success",
                        input_path=str(out_path / "image_intake/image_manifest.jsonl"),
                        output_paths=[
                            str(out_path / "image_intake/image_hashes.jsonl"),
                            str(out_path / "image_intake/image_similarity_candidates.jsonl")
                        ],
                        runtime_seconds=time.time() - sim_start
                    ))
                except Exception as sim_err:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="image-similarity",
                        status="failed",
                        input_path=str(out_path / "image_intake/image_manifest.jsonl"),
                        error_message=str(sim_err),
                        runtime_seconds=time.time() - sim_start
                    ))

            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="image-intake",
                    status="failed",
                    input_path=runtime_input.images_dir,
                    error_message=str(e),
                    runtime_seconds=time.time() - m_start
                ))
                module_statuses.append(EvidenceModuleStatus(
                    module_name="image-similarity",
                    status="failed",
                    error_message="Parent image-intake failed",
                    runtime_seconds=0.0
                ))

        # 3. Table Intake & Numeric Review
        table_artifact_count = _count_table_input_artifacts(runtime_input.tables_dir)
        if skip_tables or not Path(runtime_input.tables_dir).exists():
            table_skip_reason = "skipped_by_configuration" if skip_tables else "missing_input_directory"
            module_statuses.append(EvidenceModuleStatus(
                module_name="table-intake",
                status="skipped",
                input_artifact_count=table_artifact_count,
                skip_reason=table_skip_reason,
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="table-numeric-review",
                status="skipped",
                input_artifact_count=table_artifact_count,
                skip_reason=table_skip_reason,
            ))
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-ruleset-review",
                status="skipped"
            ))
        else:
            m_start = time.time()
            try:
                t_manifest_jsonl, t_manifest_csv, t_profiles_jsonl, t_summary_md = run_table_intake(
                    input_dir=runtime_input.tables_dir,
                    output_dir=temp_dir / "table_intake"
                )

                safe_copy_file(t_manifest_jsonl, out_path / "table_intake/table_manifest.jsonl")
                safe_copy_file(t_manifest_csv, out_path / "table_intake/table_manifest.csv")
                safe_copy_file(t_profiles_jsonl, out_path / "table_intake/column_profiles.jsonl")
                safe_copy_file(t_summary_md, out_path / "table_intake/table_intake_summary.md")

                pv_ruleset_manifests.append(t_manifest_jsonl)
                pv_ruleset_profiles.append(t_profiles_jsonl)
                table_parsed_row_count = _manifest_parsed_row_count(t_manifest_jsonl)

                module_statuses.append(EvidenceModuleStatus(
                    module_name="table-intake",
                    status="success",
                    input_path=runtime_input.tables_dir,
                    output_paths=[
                        str(out_path / "table_intake/table_manifest.jsonl"),
                        str(out_path / "table_intake/column_profiles.jsonl")
                    ],
                    runtime_seconds=time.time() - m_start,
                    input_artifact_count=table_artifact_count,
                    parsed_row_count=table_parsed_row_count,
                ))

                # Table Numeric Review
                num_start = time.time()
                if table_artifact_count == 0:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="table-numeric-review",
                        status="skipped",
                        input_path=str(out_path / "table_intake/table_manifest.jsonl"),
                        input_artifact_count=0,
                        parsed_row_count=0,
                        finding_count=0,
                        skip_reason="no_input_artifacts",
                        runtime_seconds=time.time() - num_start,
                    ))
                elif table_parsed_row_count == 0:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="table-numeric-review",
                        status="warning",
                        input_path=str(out_path / "table_intake/table_manifest.jsonl"),
                        warnings=["Input artifacts were found, but no table rows were parsed."],
                        input_artifact_count=table_artifact_count,
                        parsed_row_count=0,
                        finding_count=0,
                        skip_reason="input_parse_failed_or_zero_rows",
                        runtime_seconds=time.time() - num_start,
                    ))
                else:
                    try:
                        num_findings_jsonl, num_summary_md = run_table_numeric_review(
                            manifest_jsonl_path=temp_dir / "table_intake/table_manifest.jsonl",
                            output_dir=temp_dir / "table_intake",
                            table_base_dir=pack_path,
                            column_profiles_path=temp_dir / "table_intake/column_profiles.jsonl",
                        )

                        safe_copy_file(num_findings_jsonl, out_path / "table_intake/table_numeric_findings.jsonl")
                        safe_copy_file(num_summary_md, out_path / "table_intake/table_numeric_summary.md")

                        module_statuses.append(EvidenceModuleStatus(
                            module_name="table-numeric-review",
                            status="success",
                            input_path=str(out_path / "table_intake/table_manifest.jsonl"),
                            output_paths=[
                                str(out_path / "table_intake/table_numeric_findings.jsonl")
                            ],
                            runtime_seconds=time.time() - num_start,
                            input_artifact_count=table_artifact_count,
                            parsed_row_count=table_parsed_row_count,
                            finding_count=_jsonl_record_count(num_findings_jsonl),
                        ))
                    except Exception as num_err:
                        module_statuses.append(EvidenceModuleStatus(
                            module_name="table-numeric-review",
                            status="failed",
                            input_path=str(out_path / "table_intake/table_manifest.jsonl"),
                            error_message=str(num_err),
                            runtime_seconds=time.time() - num_start,
                            input_artifact_count=table_artifact_count,
                            parsed_row_count=table_parsed_row_count,
                            finding_count=0,
                            skip_reason="processing_failed",
                        ))

            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="table-intake",
                    status="failed",
                    input_path=runtime_input.tables_dir,
                    error_message=str(e),
                    runtime_seconds=time.time() - m_start,
                    input_artifact_count=table_artifact_count,
                    skip_reason="intake_failed",
                ))
                module_statuses.append(EvidenceModuleStatus(
                    module_name="table-numeric-review",
                    status="failed",
                    error_message="Parent table-intake failed",
                    runtime_seconds=0.0,
                    input_artifact_count=table_artifact_count,
                    skip_reason="parent_intake_failed",
                ))
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-ruleset-review",
                    status="failed",
                    error_message="Parent table-intake failed",
                    runtime_seconds=0.0
                ))

        # 4. PV Domain Review
        pv_artifact_count = _count_table_input_artifacts(runtime_input.pv_dir)
        if skip_pv or not Path(runtime_input.pv_dir).exists():
            pv_skip_reason = "skipped_by_configuration" if skip_pv else "missing_input_directory"
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-domain-review",
                status="skipped",
                input_artifact_count=pv_artifact_count,
                skip_reason=pv_skip_reason,
            ))
        else:
            m_start = time.time()
            try:
                # Intake the PV directory first
                pv_t_manifest_jsonl, pv_t_manifest_csv, pv_t_profiles_jsonl, pv_t_summary_md = run_table_intake(
                    input_dir=runtime_input.pv_dir,
                    output_dir=temp_dir / "pv_domain_intake"
                )

                pv_ruleset_manifests.append(pv_t_manifest_jsonl)
                pv_ruleset_profiles.append(pv_t_profiles_jsonl)
                pv_intake_row_count = _manifest_parsed_row_count(pv_t_manifest_jsonl)

                if pv_artifact_count == 0:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-domain-review",
                        status="skipped",
                        input_path=runtime_input.pv_dir,
                        input_artifact_count=0,
                        parsed_row_count=0,
                        finding_count=0,
                        skip_reason="no_input_artifacts",
                        runtime_seconds=time.time() - m_start,
                    ))
                elif pv_intake_row_count == 0:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-domain-review",
                        status="warning",
                        input_path=runtime_input.pv_dir,
                        warnings=["Input artifacts were found, but no PV rows were parsed."],
                        input_artifact_count=pv_artifact_count,
                        parsed_row_count=0,
                        finding_count=0,
                        skip_reason="input_parse_failed_or_zero_rows",
                        runtime_seconds=time.time() - m_start,
                    ))
                else:
                    metric_rows, field_mapping, findings, summary = run_pv_domain_review(
                        manifest_path=pv_t_manifest_jsonl,
                        column_profiles_path=pv_t_profiles_jsonl,
                        output_dir=temp_dir / "pv_domain",
                        table_base_dir=pack_path,
                    )

                    safe_copy_file(metric_rows, out_path / "pv_domain/pv_metric_rows.jsonl")
                    safe_copy_file(field_mapping, out_path / "pv_domain/pv_field_mappings.jsonl")
                    safe_copy_file(findings, out_path / "pv_domain/pv_findings.jsonl")
                    safe_copy_file(summary, out_path / "pv_domain/pv_domain_summary.md")

                    pv_parsed_row_count = _jsonl_record_count(metric_rows)
                    pv_finding_count = _jsonl_record_count(findings)
                    pv_status = "success" if pv_parsed_row_count > 0 else "warning"
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-domain-review",
                        status=pv_status,
                        input_path=runtime_input.pv_dir,
                        output_paths=[
                            str(out_path / "pv_domain/pv_findings.jsonl")
                        ],
                        warnings=([] if pv_parsed_row_count > 0 else ["PV paths did not yield parsed rows."]),
                        runtime_seconds=time.time() - m_start,
                        input_artifact_count=pv_artifact_count,
                        parsed_row_count=pv_parsed_row_count,
                        finding_count=pv_finding_count,
                        skip_reason=(None if pv_parsed_row_count > 0 else "path_resolution_or_parse_failed"),
                    ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-domain-review",
                    status="failed",
                    input_path=runtime_input.pv_dir,
                    error_message=str(e),
                    runtime_seconds=time.time() - m_start,
                    input_artifact_count=pv_artifact_count,
                    skip_reason="processing_failed",
                ))

        # PV Ruleset Completeness Review
        rs_start = time.time()
        combined_manifest = temp_dir / "pv_ruleset_combined_manifest.jsonl"
        combined_profiles = temp_dir / "pv_ruleset_combined_profiles.jsonl"

        has_manifests = False
        with open(combined_manifest, "w", encoding="utf-8") as f_m, open(combined_profiles, "w", encoding="utf-8") as f_p:
            for m_path in pv_ruleset_manifests:
                m_path = Path(m_path)
                if m_path.exists():
                    has_manifests = True
                    with open(m_path, "r", encoding="utf-8") as f_in:
                        for line in f_in:
                            if line.strip():
                                f_m.write(line.strip() + "\n")
            for p_path in pv_ruleset_profiles:
                p_path = Path(p_path)
                if p_path.exists():
                    with open(p_path, "r", encoding="utf-8") as f_in:
                        for line in f_in:
                            if line.strip():
                                f_p.write(line.strip() + "\n")

        if has_manifests:
            try:
                from integrity_agent.workflows.pv_ruleset_review import run_pv_ruleset_review
                rs_findings, rs_summary, rs_pv_count = run_pv_ruleset_review(
                    input_path=combined_manifest,
                    column_profiles_path=combined_profiles,
                    output_dir=temp_dir / "pv_ruleset_review",
                    table_base_dir=runtime_input.package_dir
                )

                if rs_pv_count > 0:
                    safe_copy_file(rs_findings, out_path / "pv_ruleset_review/pv_ruleset_findings.jsonl")
                    safe_copy_file(rs_summary, out_path / "pv_ruleset_review/pv_ruleset_review_summary.md")

                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-ruleset-review",
                        status="success",
                        input_path=str(runtime_input.package_dir),
                        output_paths=[
                            str(out_path / "pv_ruleset_review/pv_ruleset_findings.jsonl"),
                            str(out_path / "pv_ruleset_review/pv_ruleset_review_summary.md")
                        ],
                        runtime_seconds=time.time() - rs_start
                    ))
                else:
                    module_statuses.append(EvidenceModuleStatus(
                        module_name="pv-ruleset-review",
                        status="skipped",
                        warnings=["No tables with PV metadata detected."],
                        runtime_seconds=time.time() - rs_start
                    ))
            except Exception as rs_err:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="pv-ruleset-review",
                    status="failed",
                    input_path=str(runtime_input.package_dir),
                    error_message=_format_error(rs_err, privacy_roots),
                    runtime_seconds=time.time() - rs_start
                ))
        else:
            module_statuses.append(EvidenceModuleStatus(
                module_name="pv-ruleset-review",
                status="skipped",
                warnings=["No table or PV manifests available."],
                runtime_seconds=time.time() - rs_start
            ))

        # 5. Raw PV Reconciliation
        if skip_raw_pv or not Path(runtime_input.raw_pv_dir).exists():
            module_statuses.append(EvidenceModuleStatus(
                module_name="raw-pv-reconcile",
                status="skipped"
            ))
        else:
            m_start = time.time()
            try:
                run_raw_pv_reconciliation(
                    package_dir=runtime_input.raw_pv_dir,
                    output_dir=temp_dir / "raw_pv"
                )

                # Copy all files from outputs/raw_pv to output_dir/raw_pv/
                safe_copy_file(temp_dir / "raw_pv/raw_pv_findings.jsonl", out_path / "raw_pv/raw_pv_findings.jsonl")
                safe_copy_file(temp_dir / "raw_pv/raw_pv_reconciliation_summary.md", out_path / "raw_pv/raw_pv_reconciliation_summary.md")
                safe_copy_file(temp_dir / "raw_pv/jv_metrics.jsonl", out_path / "raw_pv/jv_metrics.jsonl")
                safe_copy_file(temp_dir / "raw_pv/eqe_integration_results.jsonl", out_path / "raw_pv/eqe_integration_results.jsonl")
                safe_copy_file(temp_dir / "raw_pv/excel_formula_audit.jsonl", out_path / "raw_pv/excel_formula_audit.jsonl")

                module_statuses.append(EvidenceModuleStatus(
                    module_name="raw-pv-reconcile",
                    status="success",
                    input_path=runtime_input.raw_pv_dir,
                    output_paths=[
                        str(out_path / "raw_pv/raw_pv_findings.jsonl")
                    ],
                    runtime_seconds=time.time() - m_start
                ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="raw-pv-reconcile",
                    status="failed",
                    input_path=runtime_input.raw_pv_dir,
                    error_message=str(e),
                    runtime_seconds=time.time() - m_start
                ))

        # 6. Unified Evidence Index Aggregation
        index_start = time.time()
        unified_findings = []
        processed_keys = set()

        finding_files = [
            temp_dir / "image_intake/image_findings.jsonl",
            temp_dir / "image_intake/image_similarity_candidates.jsonl",
            temp_dir / "table_intake/table_numeric_findings.jsonl",
            temp_dir / "pv_domain/pv_findings.jsonl",
            temp_dir / "raw_pv/raw_pv_findings.jsonl",
            temp_dir / "status_enrich/status_items.jsonl",
            temp_dir / "reference_scan/reference_anomalies.jsonl",
            temp_dir / "pv_ruleset_review/pv_ruleset_findings.jsonl"
        ]
        if cross_document_effective_findings is not None:
            finding_files.append(cross_document_effective_findings)
        finding_files.extend(structured_finding_files)

        finding_counter = 1
        aggregation_errors: list[str] = []
        for ff in finding_files:
            ff_path = Path(ff)
            if ff_path.exists():
                try:
                    with open(ff_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                d = _sanitize_value(
                                    json.loads(line),
                                    privacy_roots,
                                )

                                # Standardize finding format
                                rule_id = d.get("rule_id", "unknown_rule")

                                # Apply package runner risk level cap:
                                # All findings have risk levels limited to low or medium
                                # (or high for retraction/withdrawal status contexts).
                                rl = d.get("risk_level", "low").lower()
                                if rl == "high":
                                    is_retraction = any(kw in rule_id.lower() for kw in ["retract", "withdraw"])
                                    if not is_retraction:
                                        d["risk_level"] = "medium"
                                        if "risk" in d:
                                            d["risk"] = "medium"
                                src = d.get("source_file") or d.get("relative_path") or d.get("relative_path_a")
                                if not src:
                                    ev_list = d.get("evidence_items") or d.get("evidence") or []
                                    if ev_list:
                                        src = ev_list[0].get("source") or ev_list[0].get("relative_path")
                                if not src:
                                    src = "unknown_file"

                                d["source_file"] = src
                                safe_lang = d.get("safe_report_language", "")
                                comp_key = (rule_id, src, str(safe_lang))

                                if comp_key in processed_keys:
                                    continue
                                processed_keys.add(comp_key)

                                # Ensure finding has finding_id
                                if "finding_id" not in d:
                                    d["finding_id"] = f"UNIFIED-FIND-{finding_counter:03d}"
                                    finding_counter += 1

                                unified_findings.append(d)
                except Exception as e:
                    error = _sanitize_text(
                        f"{ff_path.name}: invalid JSON or finding record ({e})",
                        privacy_roots,
                    )
                    aggregation_errors.append(error)
                    print(f"ERROR: failed to aggregate {error}", file=sys.stderr)

        module_statuses.append(EvidenceModuleStatus(
            module_name="unified-evidence-aggregation",
            status="failed" if aggregation_errors else "success",
            input_path="module finding ledgers",
            warnings=[] if not aggregation_errors else list(aggregation_errors),
            error_message=(
                "; ".join(aggregation_errors) if aggregation_errors else None
            ),
            input_artifact_count=sum(Path(path).exists() for path in finding_files),
            parsed_row_count=len(unified_findings),
            finding_count=len(unified_findings),
            skip_reason="child_ledger_aggregation_failed" if aggregation_errors else None,
            runtime_seconds=time.time() - index_start,
        ))

        # Write unified evidence index
        unified_index_path = out_path / "unified_evidence_index.jsonl"
        with open(unified_index_path, "w", encoding="utf-8") as f:
            for finding in unified_findings:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")

        # Group counts
        findings_summary = {"low": 0, "medium": 0, "high": 0}
        for f in unified_findings:
            rl = f.get("risk_level", "low").lower()
            if rl in findings_summary:
                findings_summary[rl] += 1
            else:
                findings_summary["low"] += 1

        module_statuses.append(EvidenceModuleStatus(
            module_name="unified-evidence-index",
            status="success",
            output_paths=[str(unified_index_path)],
            runtime_seconds=time.time() - index_start,
            input_artifact_count=len(finding_files),
            parsed_row_count=len(unified_findings),
            finding_count=len(unified_findings),
        ))

        from integrity_agent.workflows.validate_ledger import validate_ledger_file

        final_ledger_validation = validate_ledger_file(unified_index_path)
        final_ledger_is_valid = (
            final_ledger_validation.ok and not aggregation_errors
        )
        if final_ledger_is_valid:
            module_statuses.append(EvidenceModuleStatus(
                module_name="unified-ledger-validation",
                status="success",
                input_path=str(unified_index_path),
                output_paths=[str(unified_index_path)],
                input_artifact_count=1,
                parsed_row_count=final_ledger_validation.records,
                finding_count=len(unified_findings),
            ))
        else:
            validation_details = "; ".join(
                [
                    *(issue.format() for issue in final_ledger_validation.issues),
                    *aggregation_errors,
                ]
            )
            module_statuses.append(EvidenceModuleStatus(
                module_name="unified-ledger-validation",
                status="failed",
                input_path=str(unified_index_path),
                error_message=validation_details,
                input_artifact_count=1,
                parsed_row_count=final_ledger_validation.records,
                finding_count=len(unified_findings),
                skip_reason="final_ledger_validation_failed",
            ))

        # 7. Final Reader Report
        report_start = time.time()
        summary_md_path = out_path / "review_package_summary.md"
        if not final_ledger_is_valid:
            module_statuses.append(EvidenceModuleStatus(
                module_name="report-reader-review",
                status="skipped",
                input_path=str(unified_index_path),
                warnings=["Final ledger validation failed; report generation was skipped"],
                skip_reason="invalid_final_ledger",
                runtime_seconds=time.time() - report_start,
            ))
        else:
            try:
                write_reader_review_report(
                    findings_path=unified_index_path,
                    output_path=summary_md_path,
                    artifact_root=out_path,
                )
                module_statuses.append(EvidenceModuleStatus(
                    module_name="report-reader-review",
                    status="success",
                    input_path=str(unified_index_path),
                    output_paths=[str(summary_md_path)],
                    runtime_seconds=time.time() - report_start
                ))
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="report-reader-review",
                    status="failed",
                    input_path=str(unified_index_path),
                    error_message=str(e),
                    runtime_seconds=time.time() - report_start
                ))

        # 8. HTML Dashboard
        dash_start = time.time()
        dashboard_html_path = out_path / "review_package_dashboard.html"
        if not final_ledger_is_valid:
            module_statuses.append(EvidenceModuleStatus(
                module_name="report-review-package-html",
                status="skipped",
                input_path=str(unified_index_path),
                warnings=["Final ledger validation failed; dashboard generation was skipped"],
                skip_reason="invalid_final_ledger",
                runtime_seconds=time.time() - dash_start,
            ))
        else:
            try:
                run_report_review_package_html(
                    unified_index=str(unified_index_path),
                    output_path=str(dashboard_html_path),
                    locale=locale,
                )
                module_statuses.append(EvidenceModuleStatus(
                    module_name="report-review-package-html",
                    status="success",
                    input_path=str(unified_index_path),
                    output_paths=[str(dashboard_html_path)],
                    runtime_seconds=time.time() - dash_start
                ))
                if summary_md_path.exists():
                    with open(summary_md_path, "a", encoding="utf-8") as f_summary:
                        f_summary.write(
                            "\n## Interactive Review Dashboard\n"
                            f"- A bilingual interactive web dashboard has been generated at: `{dashboard_html_path.name}`\n"
                        )
            except Exception as e:
                module_statuses.append(EvidenceModuleStatus(
                    module_name="report-review-package-html",
                    status="failed",
                    input_path=str(unified_index_path),
                    error_message=str(e),
                    runtime_seconds=time.time() - dash_start
                ))

        # Sanitize only this run's owned staged artifacts. Existing unrelated
        # files in the final output directory are never traversed or rewritten.
        _sanitize_owned_artifacts(out_path, privacy_roots)

        # Publish package/output-relative status paths while retaining absolute
        # runtime paths only inside the active process.
        for module_status in module_statuses:
            module_status.input_path = _relative_if_within(
                module_status.input_path,
                pack_path,
                out_path,
                temp_dir,
            )
            module_status.output_paths = [
                _relative_if_within(path, out_path) or ""
                for path in module_status.output_paths
            ]
            module_status.warnings = [
                _sanitize_text(warning, privacy_roots)
                for warning in module_status.warnings
            ]
            if module_status.error_message:
                module_status.error_message = _sanitize_text(
                    module_status.error_message,
                    privacy_roots,
                )

        # Compile run summary
        total_runtime = time.time() - start_time
        overall_status = "success"
        if any(s.status == "failed" for s in module_statuses):
            overall_status = "failed"
        elif any(s.status == "warning" for s in module_statuses):
            overall_status = "warning"

        from integrity_agent.core.risk_model import calculate_mrpi
        calculated_mrpi = calculate_mrpi(unified_findings)

        run_summary = ReviewPackageRunSummary(
            manifest=manifest,
            module_statuses=module_statuses,
            overall_status=overall_status,
            total_runtime_seconds=total_runtime,
            findings_summary=findings_summary,
            mrpi=calculated_mrpi,
        )

        # Write review_package_manifest.json
        manifest_json_path = out_path / "review_package_manifest.json"
        with open(manifest_json_path, "w", encoding="utf-8") as f:
            json.dump(run_summary.to_dict(), f, indent=2, ensure_ascii=False)

        # Write module_status.jsonl
        module_status_path = out_path / "module_status.jsonl"
        with open(module_status_path, "w", encoding="utf-8") as f:
            for s in module_statuses:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

        _sanitize_owned_artifacts(out_path, privacy_roots)
        _publish_owned_artifacts(
            out_path,
            final_out_path,
            run_workspace,
        )

        published_manifest_path = final_out_path / manifest_json_path.name
        published_status_path = final_out_path / module_status_path.name
        published_dashboard_path = final_out_path / dashboard_html_path.name
        print(
            "Wrote unified package manifest: "
            f"{display_path(published_manifest_path)}"
        )
        print(f"Wrote module statuses: {display_path(published_status_path)}")
        if published_dashboard_path.exists():
            print(
                "Wrote interactive dashboard: "
                f"{display_path(published_dashboard_path)}"
            )
        print(f"Unified evidence review completed in {total_runtime:.2f}s with status {overall_status}.")
        return run_summary

    finally:
        try:
            temp_dir_obj.cleanup()
        except Exception:
            pass

def main(args=None):
    parsed = parse_args(args)

    # Map raw-pv argument back to python variable name
    run_review_package(
        package_dir=parsed.package_dir,
        skip_images=parsed.skip_images,
        skip_tables=parsed.skip_tables,
        skip_pv=parsed.skip_pv,
        skip_raw_pv=parsed.skip_raw_pv,
        allow_network=parsed.allow_network,
        output_dir=parsed.output_dir
    )

if __name__ == "__main__":
    main()
