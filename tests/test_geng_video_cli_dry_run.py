import subprocess
import sys
from pathlib import Path

import yaml


def test_geng_video_dry_run_cli_with_fixture_index(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    transcript = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'private_transcripts' / 'BVcase.txt'
    transcript.parent.mkdir(parents=True)
    transcript.write_text('Synthetic transcript for CLI dry-run only.', encoding='utf-8')
    index = tmp_path / 'geng_video_index.yml'
    index.write_text(yaml.safe_dump({'videos': [{
        'bv_id': 'BVcase',
        'url': 'https://www.bilibili.com/video/BVcase/',
        'title': 'AI已扒出一大批顶刊数据异常',
        'uploader': 'synthetic',
        'publish_date': '2026-01-01',
        'duration': '00:03:55',
        'subtitle_status': 'synthetic_fixture',
        'transcript_private_path': str(transcript),
        'distillation_status': 'indexed',
        'warnings': [],
    }]}, sort_keys=False, allow_unicode=True), encoding='utf-8')

    result = subprocess.run([sys.executable, '-m', 'integrity_agent', 'geng-video-distill', str(index), '--dry-run', '1', '--output-dir', str(tmp_path / 'cases'), '--private-root', str(tmp_path / 'private_video_corpora' / 'geng_bilibili')], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert 'Wrote geng video case cards' in result.stdout
    cards = list((tmp_path / 'cases').glob('*.yml'))
    assert len(cards) == 1
