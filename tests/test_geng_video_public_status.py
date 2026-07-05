import pytest

from integrity_agent.workflows.geng_video_distillation import GengVideoSafetyError, validate_geng_video_case_card


def base_card(status='allegation'):
    return {
        'case_id': 'case1',
        'source_type': 'bilibili_video',
        'source_url': 'https://www.bilibili.com/video/BVcase/',
        'bv_id': 'BVcase',
        'video_title': 'synthetic title',
        'transcript_confidence': 'synthetic_fixture',
        'case_kind': 'specific_paper_case',
        'field': 'numeric_table_integrity',
        'paper_identifiers': [],
        'public_status': status,
        'public_status_basis': 'Bilibili video only.',
        'video_raised_risk_signals': ['candidate table anomaly'],
        'evidence_patterns': ['numeric_terminal_digit_cluster'],
        'detector_candidates': ['numeric_terminal_digit_cluster_from_video_cases'],
        'manual_verification_needed': ['original paper and raw data'],
        'false_positive_risks': ['rounding'],
        'safe_report_language': 'Candidate risk signal requiring independent verification.',
        'limitations': ['not independently verified'],
        'private_notes_reference': 'local_private_note_available_not_public',
    }


def test_allegation_requires_not_independently_verified():
    card = base_card('allegation')
    card['limitations'] = []
    with pytest.raises(GengVideoSafetyError):
        validate_geng_video_case_card(card)


def test_confirmed_misconduct_requires_official_source():
    card = base_card('confirmed_misconduct')
    card['limitations'] = []
    with pytest.raises(GengVideoSafetyError):
        validate_geng_video_case_card(card)


def test_methodology_only_is_allowed_for_methodology_note():
    card = base_card('methodology_only')
    card['case_kind'] = 'methodology_note'
    card['limitations'] = []
    validate_geng_video_case_card(card)
