import subprocess
import sys
from pathlib import Path

import yaml


def safe_card():
    return {
        'case_id': 'safe_case',
        'source_type': 'bilibili_video',
        'source_url': 'https://www.bilibili.com/video/BVsafe/',
        'bv_id': 'BVsafe',
        'video_title': 'synthetic title',
        'transcript_confidence': 'synthetic_fixture',
        'case_kind': 'specific_paper_case',
        'field': 'numeric_table_integrity',
        'paper_identifiers': [],
        'public_status': 'allegation',
        'public_status_basis': 'Bilibili video only; no official source in fixture.',
        'video_raised_risk_signals': ['candidate numeric anomaly'],
        'evidence_patterns': ['numeric_terminal_digit_cluster'],
        'detector_candidates': ['numeric_terminal_digit_cluster_from_video_cases'],
        'manual_verification_needed': ['original paper and raw data'],
        'false_positive_risks': ['rounding'],
        'safe_report_language': 'Candidate risk signal requiring independent verification.',
        'limitations': ['not independently verified'],
        'private_notes_reference': 'local_private_note_available_not_public',
    }


def test_geng_video_safety_check_cli_passes_safe_card(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    (case_dir / 'safe_case.yml').write_text(yaml.safe_dump(safe_card(), sort_keys=False, allow_unicode=True), encoding='utf-8')

    result = subprocess.run([sys.executable, '-m', 'integrity_agent', 'geng-video-safety-check', str(case_dir)], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert 'Safety check passed' in result.stdout


def test_geng_video_safety_check_cli_blocks_forbidden_phrase(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    card = safe_card()
    card['safe_report_language'] = 'fraud confirmed'
    (case_dir / 'unsafe_case.yml').write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True), encoding='utf-8')

    result = subprocess.run([sys.executable, '-m', 'integrity_agent', 'geng-video-safety-check', str(case_dir)], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 2
    assert 'forbidden phrase' in result.stderr.lower()


def test_geng_video_safety_check_cli_blocks_private_path_leak(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    card = safe_card()
    card['private_notes_reference'] = 'D:/PrivateProject/private_notes/safe_case.yml'
    (case_dir / 'unsafe_path_case.yml').write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True), encoding='utf-8')

    result = subprocess.run([sys.executable, '-m', 'integrity_agent', 'geng-video-safety-check', str(case_dir)], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 2
    assert 'private/local path fragment' in result.stderr.lower()


def test_geng_video_safety_check_cli_blocks_verdict_like_public_title(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    card = safe_card()
    card['video_title'] = 'synthetic title with 造假 wording'
    (case_dir / 'unsafe_title_case.yml').write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True), encoding='utf-8')

    result = subprocess.run([sys.executable, '-m', 'integrity_agent', 'geng-video-safety-check', str(case_dir)], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 2
    assert 'public video_title contains verdict-like term' in result.stderr.lower()
