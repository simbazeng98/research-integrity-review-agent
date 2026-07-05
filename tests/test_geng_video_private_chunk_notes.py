import yaml

from integrity_agent.workflows.geng_video_distillation import distill_geng_video_cases


def test_chunk_notes_are_private_not_public(tmp_path):
    transcript = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'private_transcripts' / 'BVchunk.txt'
    transcript.parent.mkdir(parents=True)
    transcript.write_text('Synthetic transcript. Figure 2 is discussed as a candidate visual reuse signal.', encoding='utf-8')
    index = tmp_path / 'index.yml'
    index.write_text(yaml.safe_dump({'videos': [{
        'bv_id': 'BVchunk', 'url': 'https://www.bilibili.com/video/BVchunk/', 'title': '北中医论文图像问题讨论',
        'uploader': 'synthetic', 'publish_date': '2026-01-01', 'duration': '00:02:54', 'subtitle_status': 'synthetic_fixture',
        'transcript_private_path': str(transcript), 'distillation_status': 'indexed', 'warnings': []
    }]}, sort_keys=False, allow_unicode=True), encoding='utf-8')

    paths = distill_geng_video_cases(index, output_dir=tmp_path / 'public_cases', private_root=tmp_path / 'private_video_corpora' / 'geng_bilibili', dry_run=1)
    card = yaml.safe_load(paths[0].read_text(encoding='utf-8'))
    private_ref = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'private_chunk_notes' / 'BVchunk_chunk_notes.yml'

    assert card['private_notes_reference'] == 'local_private_note_available_not_public'
    assert card['private_notes_available'] is True
    assert private_ref.exists()
    assert 'private_chunk_notes' in str(private_ref).replace('\\', '/')
    assert not (tmp_path / 'public_cases' / 'private_chunk_notes').exists()
