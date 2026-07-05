from pathlib import Path

import yaml

from integrity_agent.workflows.geng_video_distillation import distill_geng_video_cases


def test_geng_video_case_card_schema_from_synthetic_index(tmp_path):
    private_transcript = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'private_transcripts' / 'BVcase.txt'
    private_transcript.parent.mkdir(parents=True)
    private_transcript.write_text('Synthetic transcript: a paper table is discussed, with no official source mentioned.', encoding='utf-8')
    index_path = tmp_path / 'knowledge_base' / 'video_index' / 'geng_video_index.yml'
    index_path.parent.mkdir(parents=True)
    index_path.write_text(yaml.safe_dump({'videos': [{
        'bv_id': 'BVcase',
        'url': 'https://www.bilibili.com/video/BVcase/',
        'title': '用AI复核同济被举报论文 结论不同',
        'uploader': 'synthetic',
        'publish_date': '2026-01-01',
        'duration': '00:04:24',
        'subtitle_status': 'synthetic_fixture',
        'transcript_private_path': str(private_transcript),
        'distillation_status': 'indexed',
        'warnings': [],
    }]}, sort_keys=False, allow_unicode=True), encoding='utf-8')

    case_paths = distill_geng_video_cases(index_path, output_dir=tmp_path / 'knowledge_base' / 'cases' / 'geng_video_cases', private_root=tmp_path / 'private_video_corpora' / 'geng_bilibili', dry_run=1)

    card = yaml.safe_load(case_paths[0].read_text(encoding='utf-8'))
    required = {'case_id', 'source_type', 'source_url', 'bv_id', 'video_title', 'transcript_confidence', 'case_kind', 'field', 'paper_identifiers', 'public_status', 'public_status_basis', 'video_raised_risk_signals', 'evidence_patterns', 'detector_candidates', 'manual_verification_needed', 'false_positive_risks', 'safe_report_language', 'limitations', 'private_notes_reference'}
    assert required <= set(card)
    assert card['private_notes_reference'] == 'local_private_note_available_not_public'
    assert card['source_type'] == 'bilibili_video'
    assert card['public_status'] == 'allegation'
    assert 'not independently verified' in card['limitations']
    assert 'risk signal' in card['safe_report_language'].lower() or 'candidate' in card['safe_report_language'].lower()
    public_text = case_paths[0].read_text(encoding='utf-8')
    assert 'Synthetic transcript:' not in public_text
