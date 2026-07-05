import yaml

from integrity_agent.workflows.geng_video_distillation import generate_geng_video_rule_candidates


def test_geng_video_rule_candidate_schema(tmp_path):
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    case = {
        'case_id': 'video_case_1',
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
        'video_raised_risk_signals': ['candidate numeric anomaly'],
        'evidence_patterns': ['numeric_terminal_digit_cluster', 'fixed_delta_between_columns'],
        'detector_candidates': ['numeric_terminal_digit_cluster_from_video_cases', 'numeric_fixed_delta_between_columns_from_video_cases'],
        'manual_verification_needed': ['raw data'],
        'false_positive_risks': ['rounding'],
        'safe_report_language': 'Candidate risk signal requiring verification.',
        'limitations': ['not independently verified'],
        'private_notes_reference': 'local_private_note_available_not_public',
    }
    (case_dir / 'video_case_1.yml').write_text(yaml.safe_dump(case, sort_keys=False, allow_unicode=True), encoding='utf-8')

    paths = generate_geng_video_rule_candidates(case_dir, output_dir=tmp_path / 'rules')

    assert paths
    candidate = yaml.safe_load(paths[0].read_text(encoding='utf-8'))
    required = {'source_case_ids', 'evidence_pattern', 'input_required', 'algorithm_sketch', 'risk_ceiling', 'false_positive_risks', 'manual_verification_needed', 'safe_report_language', 'implementation_priority'}
    assert required <= set(candidate)
    assert 'video_case_1' in candidate['source_case_ids']
    assert candidate['risk_ceiling'] == 'risk_signal_only'
