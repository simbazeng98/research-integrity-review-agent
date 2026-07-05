from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageHashEncoding:
    """Represents the perceptual hash encodings computed for an image file."""
    image_id: str
    relative_path: str
    dhash: str
    phash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "relative_path": self.relative_path,
            "dhash": self.dhash,
            "phash": self.phash,
        }


@dataclass
class ImageSimilarityCandidate:
    """Represents a pair of visually similar candidate images."""
    candidate_id: str
    rule_id: str
    image_id_a: str
    image_id_b: str
    relative_path_a: str
    relative_path_b: str
    hash_method: str
    hamming_distance: int
    threshold: int
    risk_level: str
    safe_report_language: str
    alternative_explanations: list[str] = field(default_factory=list)
    false_positive_risks: list[str] = field(default_factory=list)
    manual_verification: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rule_id": self.rule_id,
            "image_id_a": self.image_id_a,
            "image_id_b": self.image_id_b,
            "relative_path_a": self.relative_path_a,
            "relative_path_b": self.relative_path_b,
            "hash_method": self.hash_method,
            "hamming_distance": self.hamming_distance,
            "threshold": self.threshold,
            "risk_level": self.risk_level,
            "safe_report_language": self.safe_report_language,
            "alternative_explanations": self.alternative_explanations,
            "false_positive_risks": self.false_positive_risks,
            "manual_verification": self.manual_verification,
            "limitations": self.limitations,
        }


@dataclass
class ImageSimilarityRunSummary:
    """Run metrics and candidate list for perceptual similarity analysis."""
    hash_method: str
    threshold: int
    total_images: int
    candidate_pairs_count: int
    exact_duplicates_skipped: int
    candidates: list[ImageSimilarityCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash_method": self.hash_method,
            "threshold": self.threshold,
            "total_images": self.total_images,
            "candidate_pairs_count": self.candidate_pairs_count,
            "exact_duplicates_skipped": self.exact_duplicates_skipped,
            "candidates": [c.to_dict() for c in self.candidates],
        }
