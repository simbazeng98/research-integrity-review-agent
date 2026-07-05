from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from faster_whisper import WhisperModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrity_agent.workflows.geng_video_distillation import (
    PUBLIC_PRIVATE_NOTE_REDACTION,
    PUBLIC_TITLE_REDACTION_REASON,
    RULE_CANDIDATE_LIBRARY,
    generate_geng_video_rule_candidates,
    safety_check_geng_video_cases,
    validate_geng_video_case_card,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = PROJECT_ROOT / "private_video_corpora" / "geng_bilibili"
PUBLIC_CASE_DIR = PROJECT_ROOT / "knowledge_base" / "cases" / "geng_video_cases"
PUBLIC_INDEX = PROJECT_ROOT / "knowledge_base" / "video_index" / "geng_video_index.yml"
RULE_DIR = PROJECT_ROOT / "knowledge_base" / "detector_rule_candidates" / "geng_video_distilled"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "geng_video_distillation"

KNOWN_AUDIO_IDS = {"30280", "30232", "30216", "30281", "30250"}

FORBIDDEN_PUBLIC_LONG_QUOTE_LIMIT = 260


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def public_video_title(bvid: str) -> str:
    return f"Geng Bilibili video {bvid} ({PUBLIC_TITLE_REDACTION_REASON})"


def ensure_dirs() -> None:
    for p in [
        PRIVATE_ROOT / "raw_metadata",
        PRIVATE_ROOT / "private_transcripts",
        PRIVATE_ROOT / "private_chunk_notes",
        PRIVATE_ROOT / "private_audio",
        PRIVATE_ROOT / "local_source_manifests",
        PRIVATE_ROOT / "verification_workbench",
        PUBLIC_CASE_DIR,
        PUBLIC_INDEX.parent,
        RULE_DIR,
        OUTPUT_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def clean_m4s(src: Path, dest: Path) -> None:
    raw = src.read_bytes()
    if raw.startswith(b"000000000"):
        raw = raw[9:]
    dest.write_bytes(raw)


def probe_codec(path: Path) -> str:
    result = subprocess.run(
        ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_streams", "-of", "json", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return ""
    streams = data.get("streams") or []
    if not streams:
        return ""
    return str(streams[0].get("codec_type") or "")


def choose_audio_m4s(video_dir: Path) -> tuple[Path | None, list[dict[str, str]]]:
    clean_dir = PRIVATE_ROOT / "private_audio" / "_clean_m4s"
    clean_dir.mkdir(parents=True, exist_ok=True)
    probes: list[dict[str, str]] = []
    fallback: Path | None = None
    for src in sorted(video_dir.glob("*.m4s")):
        suffix_id = src.stem.split("-")[-1]
        clean = clean_dir / f"{video_dir.name}_{src.name}"
        clean_m4s(src, clean)
        codec_type = probe_codec(clean)
        probes.append({"source": src.as_posix(), "clean_private_path": rel(clean), "codec_type": codec_type, "suffix_id": suffix_id})
        if codec_type == "audio":
            return clean, probes
        if suffix_id in KNOWN_AUDIO_IDS:
            fallback = clean
    return fallback, probes


def extract_wav(audio_m4s: Path, bvid: str) -> Path:
    wav = PRIVATE_ROOT / "private_audio" / f"{bvid}.wav"
    if wav.exists() and wav.stat().st_size > 1000:
        return wav
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(audio_m4s),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav),
        ],
        check=True,
    )
    return wav


def _write_private_asr_transcript(transcript_path: Path, rows: list[dict[str, Any]], duration: str = "cached") -> None:
    lines: list[str] = [
        "# PRIVATE ASR transcript — do not commit/publicize full text",
        "# Engine: faster-whisper; model: small; language: zh; compute_type: int8; source: local private download",
        f"# ASR duration_seconds: {duration}",
        "",
    ]
    for row in rows:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        start = float(row.get("start") or 0)
        end = float(row.get("end") or 0)
        lines.append(f"[{start:.2f}-{end:.2f}] {text}")
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def transcribe_wav(model: WhisperModel, wav: Path, bvid: str) -> tuple[Path, list[dict[str, Any]]]:
    transcript_path = PRIVATE_ROOT / "private_transcripts" / f"{bvid}.txt"
    segments_json = PRIVATE_ROOT / "private_transcripts" / f"{bvid}.segments.json"
    if transcript_path.exists() and segments_json.exists():
        try:
            rows = json.loads(segments_json.read_text(encoding="utf-8"))
            existing_head = transcript_path.read_text(encoding="utf-8", errors="ignore")[:300]
            if "PRIVATE ASR transcript" not in existing_head:
                _write_private_asr_transcript(transcript_path, rows)
            return transcript_path, rows
        except Exception:
            pass
    segments_iter, info = model.transcribe(
        str(wav),
        language="zh",
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
    )
    rows: list[dict[str, Any]] = []
    lines: list[str] = [
        "# PRIVATE ASR transcript — do not commit/publicize full text",
        "# Engine: faster-whisper; model: small; language: zh; compute_type: int8; source: local private download",
        f"# ASR duration_seconds: {getattr(info, 'duration', '')}",
        "",
    ]
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        row = {"start": round(float(seg.start), 2), "end": round(float(seg.end), 2), "text": text}
        rows.append(row)
        lines.append(f"[{row['start']:.2f}-{row['end']:.2f}] {text}")
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    segments_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return transcript_path, rows


def plain_text(segments: list[dict[str, Any]], max_chars: int | None = None) -> str:
    text = " ".join(str(s.get("text") or "").strip() for s in segments if s.get("text"))
    return text if max_chars is None else text[:max_chars]


def parse_dois(text: str) -> list[str]:
    dois = []
    for m in re.findall(r"10\.\d{4,9}/[^\s，,;；)）(（]+", text):
        m = m.rstrip(".。")
        if m not in dois:
            dois.append(m)
    return dois


def extract_figures_tables(text: str) -> list[str]:
    markers = []
    patterns = [r"Fig\.?\s*\d+[A-Za-z]?", r"Figure\s*\d+[A-Za-z]?", r"图\s*[一二三四五六七八九十\d]+[A-Za-z]?"]
    for pat in patterns:
        for m in re.findall(pat, text, flags=re.I):
            m = re.sub(r"\s+", " ", m.strip())
            if m not in markers:
                markers.append(m)
    return markers[:12]


def extract_named_terms(title: str, text: str) -> dict[str, list[str]]:
    corpus = f"{title}\n{text}"
    institutions = []
    for m in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,20}(?:大学|学院|医院|研究所|实验室|中心)", corpus):
        if m not in institutions:
            institutions.append(m)
    journals = []
    for token in ["Nature", "Science", "Cell", "PNAS", "JAMA", "Lancet", "NEJM", "Nature子刊", "SCI", "sci"]:
        if token.lower() in corpus.lower() and token not in journals:
            journals.append(token)
    roles = []
    for token in ["院长", "副院长", "校长", "前校长", "博导", "教授", "杰青", "本科生", "博士"]:
        if token in corpus and token not in roles:
            roles.append(token)
    return {"institutions": institutions[:12], "journals_or_labels": journals[:8], "roles_or_labels": roles[:12]}


def classify(title: str, text: str) -> tuple[str, str, list[str], list[str], list[str], list[str]]:
    corpus = f"{title}\n{text[:4000]}"
    if any(k in title for k in ["我有一计", "自查", "破学术造假"]):
        return (
            "methodology_note",
            "research_integrity_methodology",
            ["ASR/title indicates a methodology or field-governance discussion rather than a paper-specific finding"],
            ["verification_workflow", "safe_reporting_boundary"],
            ["methodology_triage_workflow_from_geng_videos"],
            ["scope of the proposed method", "formal policy/source checks", "independent expert review"],
        )
    academic_terms = ["为什么", "争议", "博导", "教授"]
    misconduct_or_paper_terms = ["造假", "数据", "论文", "nature", "Nature", "SCI", "sci", "官网", "代表作"]
    if any(k in title for k in academic_terms) and not any(k in title for k in misconduct_or_paper_terms):
        return (
            "academic_appointment_commentary",
            "academic_governance_claim_review",
            ["ASR/title raises an academic-appointment or governance discussion requiring policy/source verification, not a misconduct finding"],
            ["verification_workflow"],
            ["methodology_triage_workflow_from_geng_videos"],
            ["official university/news source", "appointment policy context", "independent expert review"],
        )
    if any(k in title for k in ["鱼油", "胶原蛋白", "口服液", "蛙跳"]):
        return (
            "public_science_claim_review",
            "public_health_claim_review",
            ["ASR/title raises a public science or health-claim verification topic, not a misconduct finding"],
            ["verification_workflow", "source_data_vs_figure_mismatch"],
            ["methodology_triage_workflow_from_geng_videos", "source_data_vs_figure_mismatch"],
            ["original cited papers", "clinical or mechanistic evidence quality", "expert/statistical review", "formal regulatory or guideline context"],
        )
    if any(k in title for k in ["40多篇", "10篇", "大批", "多篇", "一大批"]):
        case_kind = "multi_case_video"
    else:
        case_kind = "specific_paper_case"
    if any(k in corpus for k in ["图", "图片", "显微", "条带", "WB", "Western", "免疫", "重复"]):
        field = "image_integrity"
        patterns = ["same_panel_recolored_or_relabelled", "microscopy_field_reuse_candidate", "western_blot_lane_reuse_candidate", "source_data_vs_figure_mismatch"]
        candidates = ["image_same_panel_recolored_or_relabelled", "microscopy_field_reuse_candidate", "western_blot_lane_reuse_candidate", "source_data_vs_figure_mismatch"]
        signals = ["ASR/title raises a candidate figure/image or source-data consistency concern requiring original figure/source-image review"]
        verification = ["original paper figures", "uncropped/source images", "raw/source data", "journal/institution status"]
    elif any(k in corpus for k in ["数据", "论文", "表", "官网", "代表作", "Nature", "nature", "SCI", "sci"]):
        field = "numeric_or_source_data_integrity"
        patterns = ["numeric_terminal_digit_cluster", "fixed_delta_between_columns", "repeated_numeric_series_template", "source_data_vs_figure_mismatch"]
        candidates = ["numeric_terminal_digit_cluster_from_video_cases", "numeric_fixed_delta_between_columns_from_video_cases", "repeated_numeric_series_template", "source_data_vs_figure_mismatch"]
        signals = ["ASR/title raises a candidate paper data/source-data integrity concern requiring original paper/source-data review"]
        verification = ["original paper", "supplementary/source data", "independent recalculation", "journal/institution status"]
    else:
        field = "research_integrity_video_review"
        patterns = ["verification_workflow", "source_data_vs_figure_mismatch"]
        candidates = ["methodology_triage_workflow_from_geng_videos", "source_data_vs_figure_mismatch"]
        signals = ["ASR/title raises a research-integrity or science-claim review lead requiring independent verification"]
        verification = ["original source", "formal status check", "expert review"]
    if "官网" in corpus:
        signals.append("ASR/title references a possible official-webpage/source-data discrepancy; verify against the cited webpage and archived source")
    if "Nature" in corpus or "nature" in corpus:
        signals.append("ASR/title references a Nature-family or high-profile journal context; verify exact paper identity before any status upgrade")
    return case_kind, field, signals, patterns, candidates, verification


def chunk_private_notes(bvid: str, title: str, segments: list[dict[str, Any]], metadata: dict[str, Any], transcript_path: Path, wav_path: Path | None) -> Path:
    note_path = PRIVATE_ROOT / "private_chunk_notes" / f"{bvid}_chunk_notes.yml"
    chunks = []
    current = []
    for seg in segments:
        current.append(seg)
        if len(current) >= 12:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    if not chunks:
        chunks = [[]]
    out_chunks = []
    for i, ch in enumerate(chunks, start=1):
        text = plain_text(ch, 420)
        start = ch[0]["start"] if ch else 0
        end = ch[-1]["end"] if ch else 0
        out_chunks.append(
            {
                "chunk_id": f"chunk_{i:03d}",
                "timestamp_range": f"{start:.2f}-{end:.2f}",
                "private_asr_excerpt": text,
                "doi_candidates": parse_dois(text),
                "figure_or_table_candidates": extract_figures_tables(text),
                "risk_signal_keywords": sorted(set(re.findall(r"数据|论文|造假|重复|官网|图片|图|院长|杰青|Nature|SCI|实验|表", text, flags=re.I))),
                "method_reuse_verification_needed": [
                    "extract only the repeatable checking pattern",
                    "test the pattern on benign controls before using it as a detector",
                    "do not infer the original paper outcome from this chunk note",
                ],
            }
        )
    note = {
        "bv_id": bvid,
        "video_title": title,
        "privacy": "PRIVATE chunk notes; do not copy excerpts into public case cards",
        "source_download_dir": metadata.get("local_download_dir"),
        "private_transcript_path": rel(transcript_path),
        "private_audio_path": rel(wav_path) if wav_path else None,
        "asr_engine": "faster-whisper small int8 zh",
        "chunks": out_chunks,
    }
    note_path.write_text(yaml.safe_dump(note, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    return note_path


def make_case_card(info: dict[str, Any], transcript_path: Path, segments: list[dict[str, Any]], note_path: Path) -> dict[str, Any]:
    bvid = info["bvid"]
    title = info["title"]
    text = plain_text(segments)
    source_case_kind, field, signals, patterns, candidates, verification = classify(title, text)

    # Simba's July-2026 instruction: use Geng videos as method distillation only.
    # Do not spend this batch on whether named original papers were retracted or
    # how official announcements framed them. Those checks are a separate
    # downstream task if a paper-specific report is ever needed.
    # Read-only backward compatibility: old cards may contain the retired
    # public_video_claim_status_tracker token. No new tracker files are generated.
    patterns = [p for p in patterns if p not in {"public_video_claim_status_tracker", "status_tracking"}]
    candidates = [c for c in candidates if c != "public_video_claim_status_tracker"]
    if "methodology_triage_workflow_from_geng_videos" not in candidates:
        candidates.append("methodology_triage_workflow_from_geng_videos")
    if not patterns:
        patterns = ["verification_workflow", "safe_reporting_boundary"]
    signals = signals + [
        "This card intentionally distills Geng's repeatable checking method only; it does not evaluate the original paper's retraction or official-announcement status."
    ]
    verification = [
        "method transfer only: confirm the risk-signal pattern can be operationalized without asserting the original-paper outcome",
        "validate the candidate method on independent positive examples and benign controls",
        "if later used for a paper-specific report, verify original paper/source data separately",
    ]

    dois = parse_dois(text)
    paper_identifiers = [{"doi": d, "identifier_source": "private_asr_transcript", "verification_status": "method_context_only_not_status_verification"} for d in dois]
    public_status = "methodology_only"
    limitations = [
        "Method reuse only: this card does not claim whether any named original paper was retracted, corrected, reliable, or unreliable.",
        "Bilibili video content and ASR transcript are not official investigation conclusions.",
        "Private ASR transcript may contain recognition errors; verify against the original video before extracting a method.",
        "Comments and danmaku were not used as factual evidence.",
        "No full transcript, long quote, screenshots, comments, or danmaku are stored in this public case card.",
    ]
    safe_lang = "This video is used only to distill a repeatable review method or detector idea; it does not establish any paper-specific status."
    card = {
        "case_id": f"geng_video_{bvid.lower()}",
        "source_type": "bilibili_video",
        "source_url": f"https://www.bilibili.com/video/{bvid}/",
        "bv_id": bvid,
        "video_title": public_video_title(bvid),
        "title_redaction": PUBLIC_TITLE_REDACTION_REASON,
        "uploader": info.get("uname") or info.get("uploader") or "unknown",
        "publish_date": datetime.fromtimestamp(int(info.get("pubdate") or 0)).strftime("%Y-%m-%d") if info.get("pubdate") else "unknown",
        "duration_seconds": int(info.get("duration") or 0),
        "transcript_confidence": "private_local_asr_faster_whisper_small_machine_generated",
        "case_kind": "methodology_distillation_from_geng_video",
        "method_source_case_kind": source_case_kind,
        "field": field,
        "paper_identifiers": paper_identifiers,
        "methodology_reuse_scope": "extract Geng-style review methods, detector patterns, and false-positive controls only",
        "excluded_scope": "original-paper retraction status, official-announcement interpretation, and any paper-specific misconduct conclusion",
        "video_raised_risk_signals": signals,
        "evidence_patterns": patterns,
        "detector_candidates": candidates,
        "manual_verification_needed": verification,
        "false_positive_risks": [
            "ASR may misrecognize names, institutions, figure labels, or technical terms",
            "video narration may omit context, corrections, or alternative explanations",
            "visible numeric/image similarity can arise from rounding, shared controls, templates, legitimate transformations, or metadata loss",
            "a method that works on one narrated example may fail on benign controls or a different field",
        ],
        "safe_report_language": safe_lang,
        "public_status": public_status,
        "public_status_basis": "Methodology-only distillation by user instruction; original-paper outcome and official-status claims are intentionally not evaluated in this batch.",
        "limitations": limitations,
        "private_notes_reference": PUBLIC_PRIVATE_NOTE_REDACTION,
        "private_notes_available": note_path.exists(),
    }
    validate_geng_video_case_card(card)
    return card


def main() -> int:
    parser = argparse.ArgumentParser(description="Distill a local Bilibili download folder into the Geng case-bank layout.")
    parser.add_argument(
        "source_dir",
        type=Path,
        default=PRIVATE_ROOT / "local_downloads",
        nargs="?",
        help="Local Bilibili download root; keep this path inside an ignored private folder for public releases.",
    )
    parser.add_argument("--model", default="small", help="faster-whisper model size/name")
    parser.add_argument("--limit", type=int, default=0, help="Optional max videos for debugging; 0 = all")
    parser.add_argument("--no-asr", action="store_true", help="Skip ASR and create metadata-only private status files")
    args = parser.parse_args()

    ensure_dirs()
    source = args.source_dir
    video_infos = sorted(source.glob("*/videoInfo.json"))
    if args.limit:
        video_infos = video_infos[: args.limit]
    if not video_infos:
        raise SystemExit(f"No videoInfo.json files found under {source}")

    # Clear previous public Geng video cards/candidates for a coherent all-local batch.
    for path in PUBLIC_CASE_DIR.glob("geng_video_*.yml"):
        path.unlink()
    for path in RULE_DIR.glob("*.yml"):
        path.unlink()

    model = None if args.no_asr else WhisperModel(args.model, device="cpu", compute_type="int8")
    index_videos = []
    status_rows = []
    local_manifest = []

    for n, info_path in enumerate(video_infos, start=1):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        bvid = str(info.get("bvid") or info_path.parent.name)
        title = str(info.get("title") or bvid)
        print(f"[{n}/{len(video_infos)}] {bvid} {title}", flush=True)
        info["local_download_dir"] = info_path.parent.as_posix()
        (PRIVATE_ROOT / "raw_metadata" / f"{bvid}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

        transcript_path = PRIVATE_ROOT / "private_transcripts" / f"{bvid}.txt"
        wav_path: Path | None = None
        segments: list[dict[str, Any]] = []
        media_probes: list[dict[str, str]] = []
        asr_status = "metadata_only_no_asr"
        if model is not None:
            try:
                audio_m4s, media_probes = choose_audio_m4s(info_path.parent)
                if audio_m4s is None:
                    raise RuntimeError("no audio m4s stream found")
                wav_path = extract_wav(audio_m4s, bvid)
                transcript_path, segments = transcribe_wav(model, wav_path, bvid)
                asr_status = "private_local_asr_faster_whisper_small_machine_generated"
            except Exception as exc:  # noqa: BLE001 - batch should continue with explicit blocker
                asr_status = f"asr_failed:{type(exc).__name__}:{exc}"
                transcript_path.write_text(f"PRIVATE status marker only; ASR failed for {bvid}: {type(exc).__name__}: {exc}\n", encoding="utf-8")
                segments = []

        note_path = chunk_private_notes(bvid, title, segments, info, transcript_path, wav_path)
        card = make_case_card(info, transcript_path, segments, note_path)
        if asr_status.startswith("asr_failed") or asr_status == "metadata_only_no_asr":
            card["transcript_confidence"] = asr_status
            card["limitations"].append("Transcript-level method extraction was unavailable for this item; public card remains methodology-only metadata context.")
            validate_geng_video_case_card(card)
        case_path = PUBLIC_CASE_DIR / f"geng_video_{bvid.lower()}.yml"
        case_path.write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")

        index_videos.append(
            {
                "bv_id": bvid,
                "url": f"https://www.bilibili.com/video/{bvid}/",
                "title": public_video_title(bvid),
                "title_redaction": PUBLIC_TITLE_REDACTION_REASON,
                "uploader": info.get("uname") or "unknown",
                "publish_date": card.get("publish_date"),
                "duration": info.get("duration"),
                "subtitle_status": asr_status,
                "transcript_private_path": None,
                "audio_private_path": None,
                "private_transcript_available": transcript_path.exists(),
                "private_audio_available": bool(wav_path and wav_path.exists()),
                "distillation_status": "local_asr_distilled" if segments else "metadata_distilled",
                "warnings": ["Local downloaded media was used; full ASR transcript and chunk excerpts remain private/gitignored."],
            }
        )
        local_manifest.append({"bvid": bvid, "title": title, "source_dir": info_path.parent.as_posix(), "media_probes": media_probes})
        status_rows.append({"bv_id": bvid, "title": title, "case_path": rel(case_path), "public_status": card["public_status"], "case_kind": card["case_kind"], "transcript_confidence": card["transcript_confidence"]})

    index = {
        "index_id": "geng_bilibili_local_video_index_v1",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": "local_download_folder",
        "source_download_root": "local_private_source_redacted",
        "safety_note": "Full local videos/audio, ASR transcripts, chunk notes, danmaku, and screenshots remain private/gitignored. Public cards are methodology-only structured method extracts.",
        "videos": index_videos,
    }
    PUBLIC_INDEX.write_text(yaml.safe_dump(index, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    (PRIVATE_ROOT / "local_source_manifests" / "local_download_manifest.yml").write_text(yaml.safe_dump({"videos": local_manifest}, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    (OUTPUT_DIR / "local_batch_status.yml").write_text(yaml.safe_dump({"processed": status_rows}, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")

    rule_paths = generate_geng_video_rule_candidates(PUBLIC_CASE_DIR, output_dir=RULE_DIR)
    for path in rule_paths:
        rule = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rule["distillation_mode"] = "methodology_only"
        rule["excluded_scope"] = "original-paper retraction status, official-announcement interpretation, and paper-specific misconduct conclusion"
        rule["manual_verification_needed"] = [
            "turn the video-derived method into an explicit detector/checklist",
            "validate on independent positive examples and benign controls",
            "only if the method is later applied to a specific paper, inspect that paper/source data separately",
        ]
        rule["safe_report_language"] = "This detector candidate is a method distilled from Geng videos; it must not be used as a paper-specific conclusion without a separate source-data review."
        path.write_text(yaml.safe_dump(rule, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    errors = safety_check_geng_video_cases(PUBLIC_CASE_DIR)
    if errors:
        for err in errors:
            print(f"SAFETY ERROR: {err}", file=sys.stderr)
        return 2
    print(f"Wrote {len(status_rows)} public case cards")
    print(f"Wrote {len(rule_paths)} detector rule candidates")
    print(f"Index: {rel(PUBLIC_INDEX)}")
    print(f"Status: {rel(OUTPUT_DIR / 'local_batch_status.yml')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
