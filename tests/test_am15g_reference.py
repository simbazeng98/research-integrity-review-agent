from __future__ import annotations

import tempfile
from pathlib import Path
from integrity_agent.domains.photovoltaics.raw_measurements.am15g_reference import load_reference_spectrum

def test_load_reference_spectrum_fallback():
    # File does not exist, check fallback
    spectrum, warnings = load_reference_spectrum("non_existent_file.csv")
    assert len(spectrum) > 0
    assert any("not found" in w for w in warnings)

def test_load_reference_spectrum_custom_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "toy_am15g.csv"
        csv_file.write_text("wavelength,irradiance\n400,1.2\n500,1.4\n", encoding="utf-8")
        
        spectrum, warnings = load_reference_spectrum(str(csv_file))
        assert not warnings
        assert spectrum == [(400.0, 1.2), (500.0, 1.4)]
