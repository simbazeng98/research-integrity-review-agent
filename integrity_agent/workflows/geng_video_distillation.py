from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from integrity_agent.core.safety import find_runtime_safety_issues, walk_text_values

DEFAULT_SEED_URLS = [
    "https://www.bilibili.com/video/BV13E7q6qEZq/",  # specific paper/case discussion
    "https://www.bilibili.com/video/BV1GtTF6zEMT/",  # multi-case anomaly discussion
    "https://www.bilibili.com/video/BV19nGJ6CEUz/",  # methodology / field logic discussion
]

PUBLIC_CASE_REQUIRED_FIELDS = {
    "case_id",
    "source_type",
    "source_url",
    "bv_id",
    "video_title",
    "transcript_confidence",
    "case_kind",
    "field",
    "paper_identifiers",
    "public_status",
    "public_status_basis",
    "video_raised_risk_signals",
    "evidence_patterns",
    "detector_candidates",
    "manual_verification_needed",
    "false_positive_risks",
    "safe_report_language",
    "limitations",
    "private_notes_reference",
}

PUBLIC_PRIVATE_NOTE_REDACTION = "local_private_note_available_not_public"
PUBLIC_TITLE_REDACTION_REASON = "original title withheld for safe public release"

PUBLIC_STATUSES = {
    "allegation",
    "unresolved",
    "methodology_only",
    "investigation_started",
    "retracted",
    "mass_retraction",
    "settlement_or_legal_resolution",
    "confirmed_misconduct",
}

FORBIDDEN_PUBLIC_KEYS = {
    "full_transcript",
    "transcript_text",
    "raw_transcript",
    "comments",
    "comment_text",
    "danmaku",
    "bullet_comments",
    "screenshots",
    "screenshot_set",
    "user_id",
    "username",
}

FORBIDDEN_PUBLIC_TITLE_TERMS = {
    "造假",
    "学术不端",
    "fraud",
    "misconduct",
    "guilty",
}

RULE_CANDIDATE_LIBRARY: dict[str, dict[str, Any]] = {
    "numeric_terminal_digit_cluster_from_video_cases": {
        "evidence_pattern": "numeric_terminal_digit_cluster",
        "input_required": ["extracted numeric table", "paper/table locator", "measurement context"],
        "algorithm_sketch": [
            "profile terminal digits by numeric column",
            "compare against expected rounding/precision context",
            "emit only table-cell coordinates and uncertainty notes",
        ],
        "implementation_priority": "P0",
    },
    "numeric_fixed_delta_between_columns_from_video_cases": {
        "evidence_pattern": "fixed_delta_between_columns",
        "input_required": ["numeric table matrix", "column semantics", "reported units"],
        "algorithm_sketch": [
            "compute pairwise deltas and ratios between columns",
            "flag repeated offsets after rounding only when columns are nominally independent",
            "separate derived columns from measured columns",
        ],
        "implementation_priority": "P0",
    },
    "repeated_numeric_series_template": {
        "evidence_pattern": "repeated_numeric_series_template",
        "input_required": ["multiple related numeric series", "row/column labels", "source table provenance"],
        "algorithm_sketch": [
            "normalize each series",
            "search for repeated shape templates under offset/scale transforms",
            "report matched rows/columns for manual review",
        ],
        "implementation_priority": "P1",
    },
    "formulaic_curve_generation": {
        "evidence_pattern": "formulaic_curve_generation",
        "input_required": ["curve source data", "reported figure curve", "axis metadata"],
        "algorithm_sketch": [
            "fit simple parametric curves and residual patterns",
            "look for identical residual templates across independent curves",
            "require raw data and plotting script before escalation",
        ],
        "implementation_priority": "P2",
    },
    "image_same_panel_recolored_or_relabelled": {
        "evidence_pattern": "same_panel_recolored_or_relabelled",
        "input_required": ["figure panels", "panel labels", "image pixels"],
        "algorithm_sketch": [
            "compare panel structure under color transforms",
            "match edges/textures after grayscale conversion",
            "emit candidate panel pairs with transform metadata",
        ],
        "implementation_priority": "P1",
    },
    "western_blot_lane_reuse_candidate": {
        "evidence_pattern": "western_blot_lane_reuse_candidate",
        "input_required": ["western blot figure", "lane coordinates or segmentation"],
        "algorithm_sketch": [
            "segment lanes/bands",
            "compare lanes under crop/flip/scale transforms",
            "separate disclosed control reuse from suspicious reuse",
        ],
        "implementation_priority": "P1",
    },
    "microscopy_field_reuse_candidate": {
        "evidence_pattern": "microscopy_field_reuse_candidate",
        "input_required": ["microscopy panels", "condition labels", "pixel data"],
        "algorithm_sketch": [
            "match keypoints across microscopy panels",
            "test rotation/translation/crop transforms",
            "report candidate reused fields with required raw-image request",
        ],
        "implementation_priority": "P1",
    },
    "source_data_vs_figure_mismatch": {
        "evidence_pattern": "source_data_vs_figure_mismatch",
        "input_required": ["source data table", "reported figure/table", "analysis mapping"],
        "algorithm_sketch": [
            "map source values to reported values",
            "identify missing transforms or inconsistent labels",
            "emit reproducible recalculation checklist",
        ],
        "implementation_priority": "P0",
    },
    "methodology_triage_workflow_from_geng_videos": {
        "evidence_pattern": "verification_workflow",
        "input_required": ["video-derived method note", "candidate detector family", "benign-control examples"],
        "algorithm_sketch": [
            "extract the repeatable checking method rather than the original paper outcome",
            "turn the method into a detector or manual-review checklist with explicit false-positive controls",
            "validate on independent examples before using it for any paper-specific report",
        ],
        "implementation_priority": "P0",
    },
}


def ensure_geng_video_directories(project_root: Path | str = ".") -> None:
    root = Path(project_root)
    for rel in [
        "knowledge_base/video_index",
        "knowledge_base/cases/geng_video_cases",
        "knowledge_base/detector_rule_candidates/geng_video_distilled",
        "outputs/geng_video_distillation",
        "outputs/geng_video_distillation/cases",
        "outputs/geng_video_distillation/rule_candidates",
        "private_video_corpora/geng_bilibili/raw_metadata",
        "private_video_corpora/geng_bilibili/private_transcripts",
        "private_video_corpora/geng_bilibili/private_chunk_notes",
        "private_video_corpora/geng_bilibili/verification_workbench",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def ensure_seed_urls(seed_path: Path | str) -> Path:
    path = Path(seed_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("\n".join(DEFAULT_SEED_URLS) + "\n", encoding="utf-8")
    return path


def parse_seed_urls(seed_path: Path | str) -> list[str]:
    path = ensure_seed_urls(seed_path)
    urls: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        url = line.split()[0]
        urls.append(normalize_bilibili_url(url))
    return urls


def parse_bv_id(url: str) -> str:
    match = re.search(r"BV[0-9A-Za-z]+", url)
    if not match:
        raise ValueError(f"No BV id found in URL: {url}")
    return match.group(0)


def normalize_bilibili_url(url: str) -> str:
    bv_id = parse_bv_id(url)
    return f"https://www.bilibili.com/video/{bv_id}/"


def _format_duration(seconds: int | str | None) -> str:
    try:
        total = int(seconds or 0)
    except (TypeError, ValueError):
        total = 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _format_pubdate(timestamp: int | None) -> str:
    if not timestamp:
        return "unknown"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def _request_json(url: str, referer: str | None = None) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0 HermesResearchIntegrityDryRun/0.1"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_subtitle_text(subtitle_url: str) -> str:
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    data = _request_json(subtitle_url)
    body = data.get("body") or []
    lines = []
    for item in body:
        start = item.get("from", "")
        end = item.get("to", "")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"[{start}-{end}] {content}")
    return "\n".join(lines)


def fetch_bilibili_metadata(url: str) -> dict[str, Any]:
    normalized_url = normalize_bilibili_url(url)
    bv_id = parse_bv_id(normalized_url)
    warnings: list[str] = []
    metadata: dict[str, Any] = {
        "bv_id": bv_id,
        "url": normalized_url,
        "title": bv_id,
        "uploader": "unknown",
        "publish_date": "unknown",
        "duration": "00:00",
        "subtitle_status": "metadata_fetch_failed",
        "transcript_text": "",
        "warnings": warnings,
    }
    try:
        view = _request_json(
            f"https://api.bilibili.com/x/web-interface/view?bvid={urllib.parse.quote(bv_id)}",
            referer=normalized_url,
        )
        if view.get("code") != 0:
            warnings.append(f"Bilibili view API returned code={view.get('code')}: {view.get('message')}")
            return metadata
        data = view.get("data") or {}
        metadata.update(
            {
                "title": data.get("title") or bv_id,
                "uploader": (data.get("owner") or {}).get("name") or "unknown",
                "publish_date": _format_pubdate(data.get("pubdate")),
                "duration": _format_duration(data.get("duration")),
                "cid": data.get("cid"),
                "description": data.get("desc") or "",
            }
        )
        cid = data.get("cid")
        if not cid:
            metadata["subtitle_status"] = "no_cid_for_subtitle_lookup"
            warnings.append("No cid found; subtitle lookup skipped.")
            return metadata
        player = _request_json(
            f"https://api.bilibili.com/x/player/v2?bvid={urllib.parse.quote(bv_id)}&cid={urllib.parse.quote(str(cid))}",
            referer=normalized_url,
        )
        subtitles = ((player.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        metadata["subtitle_candidates"] = subtitles
        if not subtitles:
            metadata["subtitle_status"] = "no_public_subtitle_asr_not_run"
            warnings.append("No public official/AI subtitle found via Bilibili player API; ASR not run in safe dry-run.")
            return metadata
        chosen = None
        for item in subtitles:
            if item.get("lan") in {"zh-CN", "zh", "ai-zh"}:
                chosen = item
                break
        chosen = chosen or subtitles[0]
        text = _download_subtitle_text(chosen.get("subtitle_url") or "")
        metadata["transcript_text"] = text
        metadata["subtitle_status"] = f"public_subtitle:{chosen.get('lan') or 'unknown'}"
        if not text:
            warnings.append("Subtitle endpoint returned no text.")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        warnings.append(f"metadata/subtitle fetch failed: {type(exc).__name__}: {exc}")
    return metadata


def fixture_metadata_fetcher(url: str) -> dict[str, Any]:
    bv_id = parse_bv_id(url)
    title_map = {
        "BV13E7q6qEZq": "用AI复核同济被举报造假论文 结论不同",
        "BV1GtTF6zEMT": "AI已扒出一大批顶刊数据异常",
        "BV19nGJ6CEUz": "学术打假这个事，耿同学做的很好，但毫无意义——说说学术圈运作的底层逻辑",
    }
    return {
        "bv_id": bv_id,
        "url": normalize_bilibili_url(url),
        "title": title_map.get(bv_id, f"Fixture Bilibili video {bv_id}"),
        "uploader": "fixture_only",
        "publish_date": "unknown",
        "duration": "00:00",
        "subtitle_status": "fixture_metadata_only",
        "transcript_text": "Synthetic transcript fixture only; not from a real video.",
        "warnings": ["fixture metadata mode; no real Bilibili API call"],
    }


def _private_ref(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _public_video_title(bv_id: str) -> str:
    return f"Geng Bilibili video {bv_id} ({PUBLIC_TITLE_REDACTION_REASON})"


LOCAL_ONLY_SENTINEL_NAME = "LOCAL_ONLY_DO_NOT_COMMIT.txt"
LOCAL_ONLY_SENTINEL_TEXT = """LOCAL-ONLY PRIVATE CORPUS

This is a local-only private corpus directory for Bilibili/video-derived material.
It may contain raw metadata, audio, ASR transcripts, and private chunk notes.
Do not commit, publish, zip, or migrate this directory as source-controlled project content.
Public artifacts must be structured summaries only.
"""
PRIVATE_CORPUS_REQUIRED_GITIGNORE_PATTERNS = (
    "private_video_corpora/",
    "private_transcripts/",
    "private_chunk_notes/",
)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_private_corpus_preflight(private_root: Path | str, project_root: Path | str = ".") -> Path:
    """Create a local-only sentinel and verify ignored in-tree private corpora.

    The preflight does not read private corpus contents. It only checks the path
    boundary and .gitignore contract before workflows write transcripts/metadata.
    """
    root = Path(project_root).resolve()
    private = Path(private_root)
    private_abs = private.resolve() if private.is_absolute() else (root / private).resolve()
    if _is_relative_to(private_abs, root):
        gitignore = root / ".gitignore"
        if gitignore.exists():
            text = gitignore.read_text(encoding="utf-8", errors="ignore")
            missing = [pattern for pattern in PRIVATE_CORPUS_REQUIRED_GITIGNORE_PATTERNS if pattern not in text]
            if missing:
                raise ValueError(
                    "private corpus is inside the project tree but .gitignore is missing required patterns: "
                    + ", ".join(missing)
                )
        private_abs.mkdir(parents=True, exist_ok=True)
        sentinel = private_abs / LOCAL_ONLY_SENTINEL_NAME
        if not sentinel.exists():
            sentinel.write_text(LOCAL_ONLY_SENTINEL_TEXT, encoding="utf-8")
    return private_abs


def _is_fixture_metadata(metadata: dict[str, Any]) -> bool:
    return (
        "fixture" in str(metadata.get("subtitle_status") or "")
        or "fixture" in " ".join(str(w) for w in metadata.get("warnings") or [])
        or str(metadata.get("uploader") or "") == "fixture_only"
    )


def _should_preserve_existing_private_metadata(raw_path: Path, metadata: dict[str, Any]) -> bool:
    if not raw_path.exists():
        return False
    incoming_is_fixture = _is_fixture_metadata(metadata)
    if not incoming_is_fixture:
        return False
    try:
        existing = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(existing.get("local_download_dir") or existing.get("bvid") or existing.get("cid"))


def _should_preserve_existing_private_transcript(transcript_path: Path, metadata: dict[str, Any], incoming_text: str) -> bool:
    if not transcript_path.exists():
        return False
    subtitle_status = str(metadata.get("subtitle_status") or "")
    incoming_is_fixture_or_marker = "fixture" in subtitle_status or "Synthetic transcript fixture" in incoming_text
    if not incoming_is_fixture_or_marker:
        return False
    existing_head = transcript_path.read_text(encoding="utf-8", errors="ignore")[:300]
    return "PRIVATE ASR transcript" in existing_head or "local ASR" in existing_head


def build_geng_video_index(
    seed_path: Path | str,
    *,
    index_path: Path | str = Path("outputs/geng_video_distillation/geng_video_index.yml"),
    private_root: Path | str = Path("private_video_corpora/geng_bilibili"),
    fetcher: Callable[[str], dict[str, Any]] | None = None,
    write_private_cache: bool = False,
) -> Path:
    seed = ensure_seed_urls(seed_path)
    output = Path(index_path)
    private = Path(private_root)
    ensure_private_corpus_preflight(private, project_root=Path.cwd())
    ensure_geng_video_directories(Path("."))
    output.parent.mkdir(parents=True, exist_ok=True)
    (private / "raw_metadata").mkdir(parents=True, exist_ok=True)
    (private / "private_transcripts").mkdir(parents=True, exist_ok=True)
    fetch = fetcher or fetch_bilibili_metadata
    videos: list[dict[str, Any]] = []
    for url in parse_seed_urls(seed):
        metadata = fetch(url)
        bv_id = metadata.get("bv_id") or parse_bv_id(url)
        normalized_url = metadata.get("url") or normalize_bilibili_url(url)
        raw_path = private / "raw_metadata" / f"{bv_id}.json"
        transcript_text = metadata.get("transcript_text") or ""
        transcript_path = private / "private_transcripts" / f"{bv_id}.txt"
        incoming_is_fixture = _is_fixture_metadata(metadata)
        private_cache_written = False
        if write_private_cache and not incoming_is_fixture:
            if not _should_preserve_existing_private_metadata(raw_path, metadata):
                raw_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            if _should_preserve_existing_private_transcript(transcript_path, metadata, transcript_text):
                pass
            elif transcript_text:
                transcript_path.write_text(transcript_text, encoding="utf-8")
            else:
                transcript_path.write_text(
                    "No public subtitle transcript was available in this dry-run. ASR was not run; use this file only as a private status marker.\n",
                    encoding="utf-8",
                )
            private_cache_written = True
        videos.append(
            {
                "bv_id": bv_id,
                "url": normalized_url,
                "title": _public_video_title(str(bv_id)),
                "title_redaction": PUBLIC_TITLE_REDACTION_REASON,
                "uploader": metadata.get("uploader") or "unknown",
                "publish_date": metadata.get("publish_date") or "unknown",
                "duration": metadata.get("duration") or "00:00",
                "subtitle_status": metadata.get("subtitle_status") or "unknown",
                "transcript_private_path": None,
                "private_cache_written": private_cache_written,
                "distillation_status": "indexed",
                "warnings": list(metadata.get("warnings") or []),
            }
        )
    index = {
        "index_id": "geng_bilibili_video_index_v0",
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "source_seed_file": _private_ref(seed),
        "safety_note": "Full transcripts, comments, danmaku, and screenshots must remain private and must not be committed to public knowledge_base case cards.",
        "videos": videos,
    }
    output.write_text(yaml.safe_dump(index, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    return output


def _load_private_transcript(path_text: str, project_root: Path | None = None) -> str:
    path = Path(path_text)
    if not path.is_absolute() and project_root:
        path = project_root / path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_private_raw_metadata(bv_id: str, private_root: Path) -> dict[str, Any]:
    path = private_root / "raw_metadata" / f"{bv_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _parse_dois(text: str) -> list[str]:
    dois = []
    for match in re.findall(r"10\.\d{4,9}/[^\s，,;；)）(（]+", text):
        cleaned = match.rstrip(".。")
        if cleaned not in dois:
            dois.append(cleaned)
    return dois


def _parse_figure_or_table_markers(text: str) -> list[str]:
    markers = []
    for pattern in [r"Fig\.?\s*\d+[A-Za-z]?", r"Figure\s*\d+[A-Za-z]?", r"图\s*\d+[A-Za-z]?", r"表\s*\d+[A-Za-z]?"]:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            marker = re.sub(r"\s+", " ", match.strip())
            if marker not in markers:
                markers.append(marker)
    return markers


def _classify_case_kind(title: str) -> str:
    if any(token in title for token in ["方法", "底层逻辑", "启示", "学术打假这个事", "运作"]):
        return "methodology_note"
    if any(token in title for token in ["一大批", "多篇", "合集", "顶刊", "大批"]):
        return "multi_case_video"
    return "specific_paper_case"


def _signals_for_video(title: str, case_kind: str) -> tuple[str, list[str], list[str], list[str], list[str]]:
    if case_kind == "methodology_note":
        return (
            "research_integrity_methodology",
            ["video discusses methodology/workflow considerations for public research-integrity review"],
            ["verification_workflow", "safe_reporting_boundary"],
            ["methodology_triage_workflow_from_geng_videos"],
            ["method scope", "benign-control examples", "independent expert review"],
        )
    if any(token in title for token in ["图", "显微", "WB", "Western", "图像"]):
        return (
            "image_integrity",
            ["video raises a candidate image-panel or figure-consistency risk signal"],
            ["same_panel_recolored_or_relabelled", "microscopy_field_reuse_candidate", "western_blot_lane_reuse_candidate"],
            ["image_same_panel_recolored_or_relabelled", "microscopy_field_reuse_candidate", "western_blot_lane_reuse_candidate"],
            ["original figures", "uncropped source images", "journal notice status"],
        )
    if any(token in title for token in ["数据", "AI", "复核", "同济", "异常", "表"]):
        return (
            "numeric_table_integrity",
            ["video raises a candidate numeric/table anomaly risk signal"],
            ["numeric_terminal_digit_cluster", "fixed_delta_between_columns", "repeated_numeric_series_template", "source_data_vs_figure_mismatch"],
            ["numeric_terminal_digit_cluster_from_video_cases", "numeric_fixed_delta_between_columns_from_video_cases", "repeated_numeric_series_template", "source_data_vs_figure_mismatch"],
            ["original paper tables", "raw/source data", "independent recalculation", "official journal/institution status"],
        )
    return (
        "research_integrity_video_review",
        ["video raises a research-integrity risk signal requiring independent verification"],
        ["source_data_vs_figure_mismatch", "methodology_triage_workflow_from_geng_videos"],
        ["source_data_vs_figure_mismatch", "methodology_triage_workflow_from_geng_videos"],
        ["original paper", "source data", "official status"],
    )


def _transcript_confidence(subtitle_status: str) -> str:
    if subtitle_status.startswith("public_subtitle"):
        return "public_subtitle_private_copy"
    if "fixture" in subtitle_status:
        return "synthetic_fixture"
    if "no_public_subtitle" in subtitle_status:
        return "metadata_only_no_public_subtitle_asr_not_run"
    return "metadata_only_low"


def _chunk_note_for_video(video: dict[str, Any], transcript: str, private_root: Path, description: str = "") -> Path:
    bv_id = video["bv_id"]
    note_path = private_root / "private_chunk_notes" / f"{bv_id}_chunk_notes.yml"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_source = transcript or description
    excerpt = evidence_source[:280] if evidence_source else "No transcript text available in dry-run."
    title = video.get("title", "")
    case_kind = _classify_case_kind(title)
    doi_list = _parse_dois(description)
    figure_or_table = _parse_figure_or_table_markers(description)
    note = {
        "bv_id": bv_id,
        "video_title": video.get("title"),
        "chunking_mode": "dry_run_single_metadata_chunk",
        "privacy": "private chunk notes only; do not copy to public case cards",
        "chunks": [
            {
                "chunk_id": "chunk_001",
                "timestamp_range": "metadata-only",
                "paper_title": None,
                "doi": doi_list,
                "journal": None,
                "year": None,
                "figure_or_table": figure_or_table,
                "risk_signal_type": _signals_for_video(title, case_kind)[2],
                "video_displayed_evidence_private_note": excerpt,
                "official_source_mentioned": False,
                "external_verification_needed": ["original paper", "raw/source data", "official status checks"],
            }
        ],
    }
    note_path.write_text(yaml.safe_dump(note, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    return note_path


def distill_geng_video_cases(
    index_path: Path | str,
    *,
    output_dir: Path | str = Path("outputs/geng_video_distillation/cases"),
    private_root: Path | str = Path("private_video_corpora/geng_bilibili"),
    dry_run: int = 3,
) -> list[Path]:
    index_file = Path(index_path)
    data = yaml.safe_load(index_file.read_text(encoding="utf-8")) or {}
    videos = list(data.get("videos") or [])[:dry_run]
    out = Path(output_dir)
    private = Path(private_root)
    ensure_private_corpus_preflight(private, project_root=Path.cwd())
    out.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    project_root = Path.cwd()
    case_paths: list[Path] = []
    statuses: list[dict[str, Any]] = []
    for video in videos:
        title = str(video.get("title") or video.get("bv_id"))
        bv_id = str(video.get("bv_id"))
        case_kind = _classify_case_kind(title)
        field, risk_signals, patterns, candidates, verification = _signals_for_video(title, case_kind)
        transcript_path_text = str(video.get("transcript_private_path") or "")
        if not transcript_path_text and bv_id:
            inferred_transcript = private / "private_transcripts" / f"{bv_id}.txt"
            transcript_path_text = str(inferred_transcript) if inferred_transcript.exists() else ""
        transcript = _load_private_transcript(transcript_path_text, project_root=project_root)
        raw_metadata = _load_private_raw_metadata(bv_id, private)
        description = str(raw_metadata.get("description") or "")
        private_note = _chunk_note_for_video(video, transcript, private, description=description)
        public_status = "methodology_only" if case_kind == "methodology_note" else "allegation"
        limitations = [
            "Bilibili video content is not an official investigation conclusion.",
            "Comments and danmaku, if reviewed privately later, can only be leads and not factual evidence.",
            "No full transcript, long quote, screenshots, comments, or danmaku are stored in this public case card.",
        ]
        if public_status == "allegation":
            limitations.insert(0, "not independently verified")
        doi_list = _parse_dois(description)
        figure_or_table = _parse_figure_or_table_markers(description)
        paper_identifiers: list[dict[str, Any]] = []
        for doi in doi_list:
            paper_identifiers.append({"doi": doi, "identifier_source": "bilibili_video_metadata_description", "verification_status": "requires_independent_verification"})
        if figure_or_table and case_kind != "methodology_note":
            risk_signals = risk_signals + [
                f"video metadata/description references {', '.join(figure_or_table[:3])} as a locator for independent verification"
            ]
        if "1726" in description and case_kind != "methodology_note":
            risk_signals = risk_signals + ["video metadata/description raises a candidate fixed-divisor/grid concern; verify against original source data"]
        if doi_list and case_kind != "methodology_note":
            risk_signals = risk_signals + ["video metadata/description lists DOI-level examples; formal public status remains unverified in this dry-run"]
        card = {
            "case_id": f"geng_video_{bv_id.lower()}",
            "priority": "P1",
            "source_type": "bilibili_video",
            "source_url": video.get("url") or normalize_bilibili_url(bv_id),
            "bv_id": bv_id,
            "video_title": _public_video_title(bv_id),
            "title_redaction": PUBLIC_TITLE_REDACTION_REASON,
            "transcript_confidence": _transcript_confidence(str(video.get("subtitle_status") or "")),
            "case_kind": case_kind,
            "field": field,
            "paper_identifiers": paper_identifiers,
            "public_status": public_status,
            "public_status_basis": "Bilibili video dry-run only; no formal school/journal/ORI/Crossref/Retraction Watch/court/government source verified in this pass.",
            "video_raised_risk_signals": risk_signals,
            "evidence_patterns": patterns,
            "detector_candidates": candidates,
            "manual_verification_needed": verification,
            "false_positive_risks": [
                "video narration may omit context or later corrections",
                "visible numeric or image similarity can arise from rounding, shared controls, templates, legitimate transformations, or metadata loss",
                "without original paper/source data, detector outputs remain triage signals only",
            ],
            "safe_report_language": "This Bilibili video raises a candidate risk signal that requires independent verification against original paper/source data and formal public-status sources.",
            "limitations": limitations,
            "private_notes_reference": PUBLIC_PRIVATE_NOTE_REDACTION,
            "private_notes_available": private_note.exists(),
        }
        if public_status == "methodology_only":
            card["safe_report_language"] = "This methodology video can inform a candidate review workflow, but it is not a case finding and does not establish any paper-specific status."
        validate_geng_video_case_card(card)
        case_path = out / f"geng_video_{bv_id.lower()}.yml"
        case_path.write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        case_paths.append(case_path)
        statuses.append({"bv_id": bv_id, "case_path": case_path.as_posix(), "public_status": public_status, "case_kind": case_kind})
    default_summary_dir = Path("outputs/geng_video_distillation")
    try:
        out.resolve().relative_to(Path.cwd().resolve())
        summary_dir = default_summary_dir
    except ValueError:
        # Tests and ad-hoc callers may use absolute tmp output dirs; keep their
        # status side effects outside the real project outputs directory.
        summary_dir = out.parent / "geng_video_distillation_outputs"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "dry_run_status.yml").write_text(
        yaml.safe_dump({"processed": statuses}, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    return case_paths


class GengVideoSafetyError(ValueError):
    pass


def validate_geng_video_case_card(card: dict[str, Any]) -> None:
    errors: list[str] = []
    missing = PUBLIC_CASE_REQUIRED_FIELDS - set(card)
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")
    if card.get("source_type") != "bilibili_video":
        errors.append("source_type must be bilibili_video")
    status = card.get("public_status")
    if status not in PUBLIC_STATUSES:
        errors.append(f"public_status not allowed: {status}")
    if status == "allegation" and "not independently verified" not in (card.get("limitations") or []):
        errors.append("allegation must include limitation: not independently verified")
    if status == "confirmed_misconduct" and not card.get("official_or_institutional_source"):
        errors.append("confirmed_misconduct requires official_or_institutional_source")
    if not card.get("safe_report_language"):
        errors.append("missing safe_report_language")
    if not card.get("manual_verification_needed"):
        errors.append("missing manual_verification_needed")
    if not card.get("false_positive_risks"):
        errors.append("missing false_positive_risks")
    public_title = str(card.get("video_title") or "")
    lowered_title = public_title.lower()
    for term in FORBIDDEN_PUBLIC_TITLE_TERMS:
        if term.lower() in lowered_title:
            errors.append(f"public video_title contains verdict-like term: {term}")
    keys = {str(key) for key in card.keys()}
    forbidden_keys = keys & FORBIDDEN_PUBLIC_KEYS
    if forbidden_keys:
        errors.append(f"public case card contains forbidden transcript/comment/media keys: {sorted(forbidden_keys)}")
    errors.extend(find_runtime_safety_issues(card))
    text_values = walk_text_values(card)
    for value in text_values:
        if len(value) > 1200:
            errors.append("possible long quote/transcript segment found in public case card")
            break
    if errors:
        raise GengVideoSafetyError("; ".join(errors))


def safety_check_geng_video_cases(case_dir: Path | str) -> list[str]:
    errors: list[str] = []
    for path in sorted(Path(case_dir).glob("*.yml")):
        try:
            card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            validate_geng_video_case_card(card)
        except Exception as exc:  # noqa: BLE001 - validator aggregates user-facing errors
            errors.append(f"{path.name}: {exc}")
    return errors


def _load_case_cards(case_dir: Path | str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for path in sorted(Path(case_dir).glob("*.yml")):
        card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        validate_geng_video_case_card(card)
        cards.append(card)
    return cards


def generate_geng_video_rule_candidates(
    case_dir: Path | str,
    *,
    output_dir: Path | str = Path("outputs/geng_video_distillation/rule_candidates"),
) -> list[Path]:
    cards = _load_case_cards(case_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    by_candidate: dict[str, list[str]] = {}
    by_candidate_patterns: dict[str, set[str]] = {}
    for card in cards:
        for candidate in card.get("detector_candidates", []) or []:
            if candidate not in RULE_CANDIDATE_LIBRARY:
                # Read-only backward compatibility: legacy Geng cards may carry
                # the retired public_video_claim_status_tracker token, but no
                # new tracker YAML is generated.
                continue
            by_candidate.setdefault(candidate, []).append(card["case_id"])
            by_candidate_patterns.setdefault(candidate, set()).update(card.get("evidence_patterns", []) or [])
    paths: list[Path] = []
    all_case_ids = sorted({card["case_id"] for card in cards})
    methodology_case_ids = sorted({card["case_id"] for card in cards if card.get("case_kind") == "methodology_note"})
    for candidate_id in sorted(RULE_CANDIDATE_LIBRARY):
        template = RULE_CANDIDATE_LIBRARY[candidate_id]
        direct_case_ids = sorted(set(by_candidate.get(candidate_id, [])))
        source_case_ids = direct_case_ids or methodology_case_ids or all_case_ids
        rule = {
            "candidate_id": candidate_id,
            "source_case_ids": source_case_ids,
            "source_case_relationship": "direct_video_pattern" if direct_case_ids else "distillation_context_or_methodology_only",
            "evidence_pattern": template["evidence_pattern"],
            "observed_video_patterns": sorted(by_candidate_patterns.get(candidate_id, set())),
            "input_required": template["input_required"],
            "algorithm_sketch": template["algorithm_sketch"],
            "risk_ceiling": "risk_signal_only",
            "false_positive_risks": [
                "Bilibili/video-raised examples are not official findings",
                "detector candidates can be triggered by benign rounding, transformations, shared controls, or extraction errors",
                "manual source-data review is required before reporting",
            ],
            "manual_verification_needed": [
                "original paper or DOI metadata",
                "raw/source data or original images",
                "journal/institution/Crossref/Retraction Watch/court/government status check",
            ],
            "safe_report_language": "This detector candidate can only produce a video-derived risk signal requiring independent verification.",
            "implementation_priority": template["implementation_priority"],
        }
        path = out / f"{candidate_id}.yml"
        path.write_text(yaml.safe_dump(rule, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        paths.append(path)
    return paths
