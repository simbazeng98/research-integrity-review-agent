
from integrity_agent.workflows.geng_video_distillation import ensure_seed_urls


def test_seed_urls_created_when_missing(tmp_path):
    seed_path = tmp_path / 'private_video_corpora' / 'geng_bilibili' / 'seed_urls.txt'
    created = ensure_seed_urls(seed_path)

    assert created == seed_path
    text = seed_path.read_text(encoding='utf-8')
    assert 'https://www.bilibili.com/video/' in text
    assert len([line for line in text.splitlines() if line.strip() and not line.startswith('#')]) >= 3
