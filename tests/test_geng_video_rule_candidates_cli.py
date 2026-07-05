import subprocess
import sys
from pathlib import Path

import yaml


def test_geng_video_rule_candidates_cli(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'cases'
    case_dir.mkdir()
    card = {
        'case_id': 'case_cli',
        'source_type': 'bilibili_video',
        'source_url': 'https://www.bilibili.com/video/BVcase/',
        'bv_id': 'BVcase',
        'video_title': 'synthetic',
        'transcript_confidence': 'synthetic_fixture',
        'case_kind': 'specific_paper_case',
        'field': 'numeric_table_integrity',
        'paper_identifiers': [],
        'public_status': 'allegation',
        'public_status_basis': 'Bilibili only.',
        'video_raised_risk_signals': ['candidate'],
        'evidence_patterns': ['fixed_delta_between_columns'],
        'detector_candidates': ['numeric_fixed_delta_between_columns_from_video_cases'],
        'manual_verification_needed': ['raw data'],
        'false_positive_risks': ['rounding'],
        'safe_report_language': 'Candidate risk signal requiring verification.',
        'limitations': ['not independently verified'],
        'private_notes_reference': 'local_private_note_available_not_public',
    }
    (case_dir / 'case_cli.yml').write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True), encoding='utf-8')

    result = subprocess.run([sys.executable, '-m', 'integrity_agent', 'geng-video-rule-candidates', str(case_dir), '--output-dir', str(tmp_path / 'rules')], cwd=project_root, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert 'Wrote geng video rule candidates' in result.stdout
    assert list((tmp_path / 'rules').glob('*.yml'))
