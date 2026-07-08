from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from integrity_agent.core.evidence.ledger_schema import (
    EvidenceRecord,
    evidence_record_json_schema,
)
from integrity_agent.core.safety import FORBIDDEN_VERDICT_PHRASES


WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?:\\\\\?\\)?[A-Za-z]:[\\/](?![\\/])[^\s\"'<>|]+",
)
UNC_PATH_RE = re.compile(r"\\\\(?!\?\\)[^\\/\s\"'<>|]+[\\/][^\\/\s\"'<>|]+")
PRIVATE_PATH_FRAGMENTS = (
    "private_video_corpora",
    "private_transcripts",
    "private_chunk_notes",
    "raw_metadata",
    "danmaku",
    "bullet_comments",
)


@dataclass(frozen=True)
class LedgerValidationIssue:
    line: int
    kind: str
    message: str

    def format(self) -> str:
        return f"line {self.line} {self.kind}: {self.message}"


@dataclass(frozen=True)
class LedgerValidationResult:
    records: int
    issues: list[LedgerValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, item in value.items():
            strings.extend(_walk_strings(key))
            strings.extend(_walk_strings(item))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_walk_strings(item))
        return strings
    return []


def _find_forbidden_phrase(value: Any) -> str | None:
    strings = _walk_strings(value)
    for text in strings:
        lowered = text.lower()
        for phrase in FORBIDDEN_VERDICT_PHRASES:
            if phrase.lower() in lowered:
                return phrase
    return None


def _find_private_path(value: Any) -> str | None:
    strings = _walk_strings(value)
    for text in strings:
        normalized = text.replace("\\", "/")
        for fragment in PRIVATE_PATH_FRAGMENTS:
            if fragment in normalized:
                return fragment
        windows_match = WINDOWS_ABSOLUTE_PATH_RE.search(text)
        if windows_match:
            return windows_match.group(0)
        unc_match = UNC_PATH_RE.search(text)
        if unc_match:
            return unc_match.group(0)
    return None


def validate_ledger_file(path: Path | str) -> LedgerValidationResult:
    ledger_path = Path(path)
    issues: list[LedgerValidationIssue] = []
    records = 0

    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return LedgerValidationResult(
            records=0,
            issues=[LedgerValidationIssue(line=0, kind="io error", message=str(exc))],
        )

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        records += 1
        try:
            record = EvidenceRecord.model_validate_json(line)
        except ValidationError as exc:
            message = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            issues.append(LedgerValidationIssue(line=line_no, kind="schema error", message=message))
            continue
        except ValueError as exc:
            issues.append(LedgerValidationIssue(line=line_no, kind="json error", message=str(exc)))
            continue

        record_data = record.model_dump(mode="json")
        forbidden_phrase = _find_forbidden_phrase(record_data)
        if forbidden_phrase:
            issues.append(
                LedgerValidationIssue(
                    line=line_no,
                    kind="forbidden phrase",
                    message=f"blocked verdict-like phrase: {forbidden_phrase}",
                )
            )

        private_path = _find_private_path(record_data)
        if private_path:
            issues.append(
                LedgerValidationIssue(
                    line=line_no,
                    kind="private path leak",
                    message=f"local/private path fragment found: {private_path}",
                )
            )

    return LedgerValidationResult(records=records, issues=issues)


def write_ledger_json_schema(path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence_record_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path
