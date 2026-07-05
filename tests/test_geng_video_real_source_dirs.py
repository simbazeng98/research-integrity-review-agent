from pathlib import Path


def test_gitignore_contains_private_video_boundaries():
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / '.gitignore').read_text(encoding='utf-8')
    for pattern in [
        'private_video_corpora/',
        'private_transcripts/',
        'private_chunk_notes/',
        'private_screenshots/',
        'private_corpora/',
        'real_source_data/',
        'real_figures/',
        'papers_to_review/',
    ]:
        assert pattern in text
