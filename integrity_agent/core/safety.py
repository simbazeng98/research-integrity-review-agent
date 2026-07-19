from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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

PRIVATE_PATH_FRAGMENTS = (
    "private_video_corpora/",
    "private_transcripts/",
    "private_chunk_notes/",
    "private_screenshots/",
    "raw_metadata/",
    "private_audio/",
)

WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?:\\\\\?\\)?[A-Za-z]:[\\/](?![\\/])[^\s\"'<>|]+",
)
UNC_PATH_RE = re.compile(r"\\\\(?!\?\\)[^\\/\s\"'<>|]+[\\/][^\\/\s\"'<>|]+")
POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![:\w/])/(?!/)(?:[^/\s\"'<>|]+/)+[^/\s\"'<>|]+"
)

SENSITIVE_AUTH_KEYS = frozenset(
    {
        "access_token",
        "auth_token",
        "authorization",
        "cookie",
        "cookies",
        "qr",
        "qr_code",
        "qrcode",
        "refresh_token",
        "session",
        "session_id",
        "xsec_token",
    }
)
SENSITIVE_AUTH_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:access[_-]?token|auth[_-]?token|authorization|cookie|"
    r"refresh[_-]?token|session[_-]?id|xsec[_-]?token|qr(?:[_-]?code)?)\s*[:=]"
)
BEARER_AUTH_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/]+=*")
SENSITIVE_AUTH_VALUE_RE = re.compile(
    r"(?i)\b(?:access[_-]?token|auth[_-]?token|authorization|cookie|"
    r"refresh[_-]?token|session[_-]?id|xsec[_-]?token|qr(?:[_-]?code)?)"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;}\]]+)"
)


def _is_test_negative_assertion_line(line: str) -> bool:
    return any(marker in line for marker in TEST_NEGATIVE_ASSERTION_MARKERS)


def walk_text_values(value: Any) -> list[str]:
    """Return all string keys and values contained in a nested public record."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, item in value.items():
            strings.extend(walk_text_values(key))
            strings.extend(walk_text_values(item))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for item in value:
            strings.extend(walk_text_values(item))
        return strings
    return []


def walk_mapping_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, item in value.items():
            keys.append(str(key))
            keys.extend(walk_mapping_keys(item))
        return keys
    if isinstance(value, (list, tuple, set)):
        keys = []
        for item in value:
            keys.extend(walk_mapping_keys(item))
        return keys
    return []


def redact_public_text(value: object) -> str:
    """Remove private paths, authentication values, and verdict phrases from diagnostics."""

    text = str(value)
    text = SENSITIVE_AUTH_VALUE_RE.sub("<redacted-auth>", text)
    text = BEARER_AUTH_RE.sub("Bearer <redacted-auth>", text)
    text = WINDOWS_ABSOLUTE_PATH_RE.sub("<local-path>", text)
    text = UNC_PATH_RE.sub("<local-path>", text)
    text = POSIX_ABSOLUTE_PATH_RE.sub("<local-path>", text)
    for fragment in PRIVATE_PATH_FRAGMENTS:
        text = re.sub(
            re.escape(fragment),
            "<private-path>/",
            text,
            flags=re.IGNORECASE,
        )
    for phrase in FORBIDDEN_VERDICT_PHRASES:
        text = re.sub(
            re.escape(phrase),
            "<redacted-verdict-language>",
            text,
            flags=re.IGNORECASE,
        )
    return text


def find_runtime_safety_issues(value: Any) -> list[str]:
    """Validate verdict language and private paths in a runtime public record.

    This is shared by generic case-card and Geng-video validation so both
    workflows apply the same minimum publication boundary.
    """
    strings = walk_text_values(value)
    issues: list[str] = []

    for key in walk_mapping_keys(value):
        normalized_key = key.strip().lower().replace("-", "_")
        if normalized_key in SENSITIVE_AUTH_KEYS:
            issue = f"sensitive authentication field found: {normalized_key}"
            if issue not in issues:
                issues.append(issue)

    for text in strings:
        if SENSITIVE_AUTH_ASSIGNMENT_RE.search(text) or BEARER_AUTH_RE.search(text):
            issue = "sensitive authentication material found in public record"
            if issue not in issues:
                issues.append(issue)

    for text in strings:
        lowered = text.lower()
        for phrase in FORBIDDEN_VERDICT_PHRASES:
            if phrase.lower() in lowered:
                issue = f"forbidden phrase found: {phrase}"
                if issue not in issues:
                    issues.append(issue)

    for text in strings:
        normalized = text.replace("\\", "/")
        lowered = normalized.lower()
        matched_fragment = next(
            (
                fragment
                for fragment in PRIVATE_PATH_FRAGMENTS
                if fragment.lower() in lowered
            ),
            None,
        )
        if matched_fragment:
            issue = f"private/local path fragment found: {matched_fragment}"
            if issue not in issues:
                issues.append(issue)
            continue

        windows_match = WINDOWS_ABSOLUTE_PATH_RE.search(text)
        if windows_match:
            issue = f"private/local path fragment found: {windows_match.group(0)}"
            if issue not in issues:
                issues.append(issue)
            continue

        unc_match = UNC_PATH_RE.search(text)
        if unc_match:
            issue = f"private/local path fragment found: {unc_match.group(0)}"
            if issue not in issues:
                issues.append(issue)
            continue

        posix_match = POSIX_ABSOLUTE_PATH_RE.search(text)
        if posix_match:
            issue = f"private/local path fragment found: {posix_match.group(0)}"
            if issue not in issues:
                issues.append(issue)

    return issues


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
