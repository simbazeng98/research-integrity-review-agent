from pathlib import Path

import yaml

from integrity_agent.workflows.geng_video_distillation import build_geng_video_index


def fixture_like_fetcher(url: str) -> dict:
    bv_id = url.rstrip('/').split('/')[-1]
    return {
        'bv_id': bv_id,
        'url': url,
        'title': 'Synthetic video for schema testing',
        'uploader': 'fixture_only',
        'publish_date': '2026-01-01',
        'duration': '00:04:00',
        'subtitle_status': 'synthetic_transcript_fixture',
        'transcript_text': 'Synthetic transcript only. This is not from a real video.',
        'warnings': ['fixture metadata mode'],
    }


def live_like_fetcher(url: str) -> dict:
    bv_id = url.rstrip('/').split('/')[-1]
    return {
        'bv_id': bv_id,
        'url': url,
        'title': 'Live-like video for schema testing',
        'uploader': 'public uploader',
        'publish_date': '2026-01-01',
        'duration': '00:04:00',
        'subtitle_status': 'public_subtitle:zh-CN',
        'transcript_text': 'Short public subtitle text copied into private cache only when explicitly requested.',
        'warnings': [],
    }


def test_geng_video_index_schema_defaults_do_not_write_fixture_private_cache(tmp_path):
    seed = tmp_path / 'seed_urls.txt'
    seed.write_text('https://www.bilibili.com/video/BV1synthetic01/\n', encoding='utf-8')
    index_path = tmp_path / 'outputs' / 'geng_video_distillation' / 'geng_video_index.yml'
    private_root = tmp_path / 'private_video_corpora' / 'geng_bilibili'

    written = build_geng_video_index(seed, index_path=index_path, private_root=private_root, fetcher=fixture_like_fetcher)

    data = yaml.safe_load(written.read_text(encoding='utf-8'))
    assert data['index_id'] == 'geng_bilibili_video_index_v0'
    video = data['videos'][0]
    for field in ['bv_id', 'url', 'title', 'uploader', 'publish_date', 'duration', 'subtitle_status', 'transcript_private_path', 'private_cache_written', 'distillation_status', 'warnings']:
        assert field in video
    assert video['transcript_private_path'] is None
    assert video['private_cache_written'] is False
    assert not (private_root / 'raw_metadata' / 'BV1synthetic01.json').exists()
    assert not (private_root / 'private_transcripts' / 'BV1synthetic01.txt').exists()


def test_geng_video_index_private_cache_requires_explicit_opt_in_and_non_fixture_metadata(tmp_path):
    seed = tmp_path / 'seed_urls.txt'
    seed.write_text('https://www.bilibili.com/video/BV1live01/\n', encoding='utf-8')
    index_path = tmp_path / 'outputs' / 'geng_video_distillation' / 'geng_video_index.yml'
    private_root = tmp_path / 'private_video_corpora' / 'geng_bilibili'

    written = build_geng_video_index(
        seed,
        index_path=index_path,
        private_root=private_root,
        fetcher=live_like_fetcher,
        write_private_cache=True,
    )

    data = yaml.safe_load(written.read_text(encoding='utf-8'))
    video = data['videos'][0]
    assert video['private_cache_written'] is True
    assert video['transcript_private_path'] is None
    assert (private_root / 'raw_metadata' / 'BV1live01.json').exists()
    assert (private_root / 'private_transcripts' / 'BV1live01.txt').exists()
