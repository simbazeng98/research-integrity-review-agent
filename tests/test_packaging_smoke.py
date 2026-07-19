from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_installs_the_packaging_frontend_used_by_the_suite():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert 'python -m pip install -e . pytest build "setuptools>=77"' in workflow


def test_packaging_smoke(tmp_path):
    """Build the package offline and verify sdist and wheel contain critical resources."""
    cmd = [
        sys.executable,
        "-m",
        "build",
        "--no-isolation",
        "--wheel",
        "--sdist",
        "--outdir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    assert result.returncode == 0, f"Build failed:\nStdout: {result.stdout}\nStderr: {result.stderr}"

    # Find the built sdist and wheel files
    wheels = list(tmp_path.glob("*.whl"))
    sdists = list(tmp_path.glob("*.tar.gz"))

    assert len(wheels) == 1, f"Expected exactly 1 wheel file, found: {wheels}"
    assert len(sdists) == 1, f"Expected exactly 1 sdist file, found: {sdists}"

    wheel_path = wheels[0]
    sdist_path = sdists[0]

    # Required resources that must be included
    expected_resources = {
        "integrity_agent/core/i18n/locales/en.yml",
        "integrity_agent/core/i18n/locales/zh.yml",
        "integrity_agent/core/reporting/templates/dashboard.html",
    }

    # Verify wheel (zip archive) contains resources
    with zipfile.ZipFile(wheel_path) as z:
        namelist = set(z.namelist())
        for res in expected_resources:
            assert res in namelist, f"Resource '{res}' was not found in wheel. Packaged files: {namelist}"

    # Verify sdist (tar.gz archive) contains resources (under prefixed folders)
    with tarfile.open(sdist_path, "r:gz") as t:
        names = t.getnames()
        for res in expected_resources:
            found = any(name.endswith(res) for name in names)
            assert found, f"Resource '{res}' was not found in sdist. Packaged files: {names}"
