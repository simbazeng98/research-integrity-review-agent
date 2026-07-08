from __future__ import annotations

import time
from typing import Any

class ReviewPackageInput:
    def __init__(
        self,
        package_dir: str,
        metadata_dir: str | None = None,
        images_dir: str | None = None,
        tables_dir: str | None = None,
        pv_dir: str | None = None,
        raw_pv_dir: str | None = None,
        references_dir: str | None = None,
    ):
        self.package_dir = package_dir
        self.metadata_dir = metadata_dir or f"{package_dir}/metadata"
        self.images_dir = images_dir or f"{package_dir}/images"
        self.tables_dir = tables_dir or f"{package_dir}/tables"
        self.pv_dir = pv_dir or f"{package_dir}/pv"
        self.raw_pv_dir = raw_pv_dir or f"{package_dir}/raw_pv"
        self.references_dir = references_dir or f"{package_dir}/references"

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_dir": self.package_dir,
            "metadata_dir": self.metadata_dir,
            "images_dir": self.images_dir,
            "tables_dir": self.tables_dir,
            "pv_dir": self.pv_dir,
            "raw_pv_dir": self.raw_pv_dir,
            "references_dir": self.references_dir,
        }

class EvidenceModuleStatus:
    def __init__(
        self,
        module_name: str,
        status: str,  # skipped / success / warning / failed
        input_path: str | None = None,
        output_paths: list[str] | None = None,
        warnings: list[str] | None = None,
        error_message: str | None = None,
        runtime_seconds: float = 0.0,
    ):
        self.module_name = module_name
        self.status = status
        self.input_path = input_path
        self.output_paths = output_paths or []
        self.warnings = warnings or []
        self.error_message = error_message
        self.runtime_seconds = runtime_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "status": self.status,
            "input_path": self.input_path,
            "output_paths": self.output_paths,
            "warnings": self.warnings,
            "error_message": self.error_message,
            "runtime_seconds": self.runtime_seconds,
        }

class ReviewPackageManifest:
    def __init__(
        self,
        package_id: str,
        inputs: ReviewPackageInput,
        created_at: float | None = None,
        version: str = "v0.2.0",
        metadata_info: dict[str, Any] | None = None,
    ):
        self.package_id = package_id
        self.inputs = inputs
        self.created_at = created_at or time.time()
        self.version = version
        self.metadata_info = metadata_info or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "inputs": self.inputs.to_dict(),
            "created_at": self.created_at,
            "version": self.version,
            "metadata_info": self.metadata_info,
        }

class ReviewPackageRunSummary:
    def __init__(
        self,
        manifest: ReviewPackageManifest,
        module_statuses: list[EvidenceModuleStatus],
        overall_status: str = "success",
        total_runtime_seconds: float = 0.0,
        findings_summary: dict[str, int] | None = None,
        mrpi: float | None = None,
        mrpi_notice: str | None = None,
    ):
        self.manifest = manifest
        self.module_statuses = module_statuses
        self.overall_status = overall_status
        self.total_runtime_seconds = total_runtime_seconds
        self.findings_summary = findings_summary or {"low": 0, "medium": 0, "high": 0}
        self.mrpi = mrpi
        self.mrpi_notice = mrpi_notice or (
            "Manual Review Priority Index (MRPI) is an estimated density of candidate anomaly signals "
            "intended for manual verification prioritization. It does NOT represent a probability of research misconduct."
        )

    def to_dict(self) -> dict[str, Any]:
        res = {
            "manifest": self.manifest.to_dict(),
            "module_statuses": [s.to_dict() for s in self.module_statuses],
            "overall_status": self.overall_status,
            "total_runtime_seconds": self.total_runtime_seconds,
            "findings_summary": self.findings_summary,
        }
        if self.mrpi is not None:
            res["mrpi"] = self.mrpi
            res["mrpi_notice"] = self.mrpi_notice
        return res
