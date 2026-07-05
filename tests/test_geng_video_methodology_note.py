import yaml

from integrity_agent.workflows.geng_video_distillation import distill_geng_video_cases


def test_methodology_video_gets_methodology_only_status(tmp_path):
    transcript = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'private_transcripts' / 'BVmethod.txt'
    transcript.parent.mkdir(parents=True)
    transcript.write_text('Synthetic methodology transcript about verification workflow and limits.', encoding='utf-8')
    index_path = tmp_path / 'index.yml'
    index_path.write_text(yaml.safe_dump({'videos': [{
        'bv_id': 'BVmethod',
        'url': 'https://www.bilibili.com/video/BVmethod/',
        'title': '学术打假这个事：说说学术圈运作的底层逻辑',
        'uploader': 'synthetic',
        'publish_date': '2026-01-01',
        'duration': '00:39:56',
        'subtitle_status': 'synthetic_fixture',
        'transcript_private_path': str(transcript),
        'distillation_status': 'indexed',
        'warnings': [],
    }]}, sort_keys=False, allow_unicode=True), encoding='utf-8')

    paths = distill_geng_video_cases(index_path, output_dir=tmp_path / 'cases', private_root=tmp_path / 'private_video_corpora' / 'geng_bilibili', dry_run=1)

    card = yaml.safe_load(paths[0].read_text(encoding='utf-8'))
    assert card['case_kind'] == 'methodology_note'
    assert card['public_status'] == 'methodology_only'
    assert 'not independently verified' not in card['limitations']
