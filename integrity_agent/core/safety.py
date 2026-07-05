from __future__ import annotations

from pathlib import Path

FORBIDDEN_VERDICT_PHRASES = [
    "造假成立",
    "学术不端成立",
    "作者造假",
    "实锤造假",
    "证明造假",
    "定性造假",
    "fraud confirmed",
    "misconduct confirmed",
    "proven fraud",
    "guilty",
    "proven fake",
    "fabricated data confirmed",
]

TEST_NEGATIVE_ASSERTION_MARKERS = (
    "FORBIDDEN_PHRASES",
    "FORBIDDEN_VERDICT_PHRASES",
    "forbidden phrase",
    "negative assertion",
    "blocks_forbidden_phrase",
    "assert phrase not in",
)

TEXT_EXTENSIONS = {".md", ".html", ".jsonl", ".json", ".yml", ".yaml", ".txt"}


def _is_test_negative_assertion_line(line: str) -> bool:
    return any(marker in line for marker in TEST_NEGATIVE_ASSERTION_MARKERS)


def scan_for_forbidden_phrases(
    path: Path | str,
    *,
    allow_test_negative_assertions: bool = True,
) -> list[dict[str, object]]:
    """Scan text files for verdict-like overclaiming phrases.

    Test files may keep literal forbidden phrases only when the line is clearly a
    negative assertion or validator fixture. This helper is intentionally simple
    and local-only so release checks can run without network access.
    """
    root = Path(path)
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    hits: list[dict[str, object]] = []
    for file_path in files:
        if file_path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel_parts = {part.lower() for part in file_path.parts}
        is_test_file = "tests" in rel_parts or file_path.name.startswith("test_")
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line_no, line in enumerate(lines, start=1):
            line_l = line.lower()
            for phrase in FORBIDDEN_VERDICT_PHRASES:
                if phrase.lower() not in line_l:
                    continue
                if allow_test_negative_assertions and is_test_file and _is_test_negative_assertion_line(line):
                    continue
                hits.append({"path": file_path.as_posix(), "line": line_no, "phrase": phrase})
    return hits
