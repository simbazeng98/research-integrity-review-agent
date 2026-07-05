from pathlib import Path


def test_toy_transcript_fixtures_are_marked_synthetic():
    project_root = Path(__file__).resolve().parents[1]
    test_files = [
        path for path in (project_root / 'tests').glob('test_geng_video_*.py')
        if path.name != 'test_geng_video_toy_transcript_policy.py'
    ]
    combined = '\n'.join(path.read_text(encoding='utf-8') for path in test_files)
    assert 'Synthetic transcript' in combined or 'synthetic transcript' in combined
    assert 'bilibili.com/video/BV' in combined
