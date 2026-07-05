from pathlib import Path


def test_geng_video_public_docs_exist_after_setup():
    project_root = Path(__file__).resolve().parents[1]
    for path in [
        project_root / 'docs' / 'GENG_VIDEO_DISTILLATION_PROTOCOL.md',
        project_root / 'docs' / 'GENG_VIDEO_CASE_CARD_SAFETY.md',
    ]:
        assert path.exists()
        text = path.read_text(encoding='utf-8')
        assert 'Bilibili' in text or 'B站' in text
        assert 'not independently verified' in text
