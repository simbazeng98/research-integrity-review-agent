import subprocess
import sys
from pathlib import Path


def test_geng_video_index_cli_creates_seed_if_missing(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    seed = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'seed_urls.txt'
    index = tmp_path / 'knowledge_base' / 'video_index' / 'geng_video_index.yml'

    private_root = tmp_path / 'private_video_corpora' / 'geng_bilibili'

    result = subprocess.run([
        sys.executable,
        '-m',
        'integrity_agent',
        'geng-video-index',
        str(seed),
        '--output',
        str(index),
        '--private-root',
        str(private_root),
        '--metadata-mode',
        'fixture',
    ], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert seed.exists()
    assert index.exists()
    assert 'Wrote geng video index' in result.stdout
