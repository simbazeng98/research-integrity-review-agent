from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from integrity_agent.core.metadata.doi import normalize_doi
from integrity_agent.core.metadata.crossref_client import fetch_crossref_work, CrossrefClientError
from integrity_agent.core.metadata.crossref_updates import parse_crossref_updates
from integrity_agent.core.rules.schema import DetectorRule, RuleExecutionResult
from integrity_agent.detectors.base import BaseDetector


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


class CrossrefRetractionDetector(BaseDetector):
    runtime_status = "active"
    execution_mode = "hybrid"
    risk_ceiling = "medium"
    requires_network = True
    requires_private_data = False

    def detect(
        self,
        package_dir: Path,
        rule: DetectorRule,
        options: dict[str, Any] | None = None,
    ) -> list[RuleExecutionResult]:
        allow_network = bool(options.get("allow_network", False)) if options else False

        # Read local toy mock file to extract target DOI/identifier
        metadata_path = package_dir / "toy_metadata_mock.yml"
        if not metadata_path.exists():
            return []

        try:
            local_meta = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            local_meta = {}

        raw_identifier = local_meta.get("identifier")
        if not raw_identifier:
            return []

        # 1. Normalize DOI
        try:
            doi = normalize_doi(raw_identifier)
        except ValueError:
            doi = str(raw_identifier).strip().lower()

        # 2. Fetch Crossref Work metadata
        try:
            work_json = fetch_crossref_work(doi, allow_network=allow_network)
            parsed = parse_crossref_updates(work_json)
            status = parsed.status
        except CrossrefClientError:
            status = "metadata_unavailable"
            parsed = None

        # 3. Handle 'no_known_update' - do not produce a risk finding
        if status == "no_known_update":
            return []

        # 4. Map risk levels and safe language
        if status == "retraction":
            risk_level = "high"
            safe_lang = "Candidate retraction metadata signal detected; verify notice text."
            observed_pattern = "Retraction/withdrawal notice found in Crossref metadata."
        elif status == "expression_of_concern":
            risk_level = "medium"
            safe_lang = "Candidate expression of concern metadata signal detected."
            observed_pattern = "Expression of concern notice found in Crossref metadata."
        elif status == "correction":
            risk_level = "low"
            safe_lang = "Candidate correction metadata signal detected."
            observed_pattern = "Correction notice found in Crossref metadata."
        elif status == "reinstatement":
            risk_level = "low"
            safe_lang = "Candidate reinstatement metadata signal detected."
            observed_pattern = "Reinstatement notice found in Crossref metadata."
        else:
            # status == "metadata_unavailable"
            risk_level = "low"
            safe_lang = "Candidate metadata unavailable signal; lookup could not be completed."
            observed_pattern = "Could not retrieve Crossref metadata."

        source_strength = "toy_or_synthetic" if doi.startswith("10.0000/") else "crossref_metadata"

        # Format related updates as evidence info
        evidence_items = []
        if parsed and parsed.updates:
            for item in parsed.updates:
                evidence_items.append({
                    "source": (
                        metadata_path.relative_to(_project_root()).as_posix()
                        if metadata_path.is_relative_to(_project_root())
                        else metadata_path.as_posix()
                    ),
                    "location": f"Crossref updates ({item.source})",
                    "observed_pattern": f"{item.update_type} notice ({item.related_doi}) published on {item.updated_date or 'unknown date'}",
                    "identifier": doi,
                    "status": status,
                    "update_doi": item.related_doi,
                })
        else:
            evidence_items.append({
                "source": (
                    metadata_path.relative_to(_project_root()).as_posix()
                    if metadata_path.is_relative_to(_project_root())
                    else metadata_path.as_posix()
                ),
                "location": "mock_public_status" if not allow_network else "Crossref API",
                "observed_pattern": observed_pattern,
                "identifier": doi,
                "status": status,
            })

        findings = [
            RuleExecutionResult(
                finding_id="RR-003",
                rule_id=rule.rule_id,
                risk_level=risk_level,
                evidence_items=evidence_items,
                manual_verification={"needed": True, "requests": list(rule.manual_verification)},
                false_positive_risks=rule.false_positive_risks,
                safe_report_language=safe_lang,
                alternative_explanations=[
                    "Metadata may describe a correction, withdrawal, or context notice rather than article-level misconduct.",
                    "Mock metadata is synthetic and may not correspond to a real DOI.",
                ],
                missing_verification_materials=rule.manual_verification,
                suggested_verification_questions=[
                    "Please verify the notice text from the publisher or authoritative metadata source.",
                    "Please distinguish retraction, correction, withdrawal, and expression of concern.",
                ],
                limitations=[
                    "This detector runs offline by default and requires --allow-network for Crossref queries.",
                ],
                metadata={
                    "detector_id": "crossref_retraction_check",
                    "source_strength": source_strength,
                    "crossref_update_status": status,
                    "runtime_status": self.runtime_status,
                    "execution_mode": self.execution_mode,
                    "risk_ceiling": self.risk_ceiling,
                    "requires_network": self.requires_network,
                    "requires_private_data": self.requires_private_data,
                },
            )
        ]
        return findings


def check_retraction_metadata(
    package_dir: Path,
    rule: DetectorRule,
    options: dict[str, Any] | None = None,
) -> list[RuleExecutionResult]:
    return CrossrefRetractionDetector().detect(package_dir, rule, options)
