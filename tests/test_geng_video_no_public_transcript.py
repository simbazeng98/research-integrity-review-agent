from pathlib import Path

import yaml

from integrity_agent.workflows.geng_video_distillation import safety_check_geng_video_cases


def test_public_case_card_does_not_store_full_transcript(tmp_path):
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    card = {
        'case_id': 'unsafe_transcript_case',
        'source_type': 'bilibili_video',
        'source_url': 'https://www.bilibili.com/video/BVcase/',
        'bv_id': 'BVcase',
        'video_title': 'synthetic title',
        'transcript_confidence': 'synthetic_fixture',
        'case_kind': 'specific_paper_case',
        'field': 'numeric_table_integrity',
        'paper_identifiers': [],
        'public_status': 'allegation',
        'public_status_basis': 'Bilibili video only.',
        'video_raised_risk_signals': ['candidate risk signal'],
        'evidence_patterns': ['numeric_terminal_digit_cluster'],
        'detector_candidates': ['numeric_terminal_digit_cluster_from_video_cases'],
        'manual_verification_needed': ['raw data'],
        'false_positive_risks': ['rounding'],
        'safe_report_language': 'Candidate risk signal requiring verification.',
        'limitations': ['not independently verified'],
        'private_notes_reference': 'local_private_note_available_not_public',
        'full_transcript': 'Synthetic but long transcript content should not be public.',
    }
    (case_dir / 'bad.yml').write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True), encoding='utf-8')

    errors = safety_check_geng_video_cases(case_dir)

    assert any('transcript' in error.lower() for error in errors)
