from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from pydantic import ValidationError

from integrity_agent.core.evidence.ledger_schema import (
    EvidenceRecord,
    evidence_record_json_schema,
)
from integrity_agent.core.safety import find_runtime_safety_issues


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
        for safety_issue in find_runtime_safety_issues(record_data):
            if safety_issue.startswith("forbidden phrase"):
                kind = "forbidden phrase"
            elif safety_issue.startswith("private/local path"):
                kind = "private path leak"
            elif safety_issue.startswith("sensitive authentication"):
                kind = "sensitive authentication material"
            else:
                kind = "runtime safety error"
            issues.append(
                LedgerValidationIssue(
                    line=line_no,
                    kind=kind,
                    message=safety_issue,
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
