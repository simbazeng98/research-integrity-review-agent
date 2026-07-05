from __future__ import annotations

import tempfile
from pathlib import Path
from integrity_agent.domains.photovoltaics.raw_measurements.eqe_spectrum_reader import read_eqe_spectrum_file

def test_eqe_spectrum_reader_percent():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "dev1_eqe.csv"
        # EQE values are mostly > 1.0 (percent format)
        csv_file.write_text("wavelength_nm,EQE\n350,50.0\n400,80.0\n", encoding="utf-8")
        
        spec = read_eqe_spectrum_file(str(csv_file))
        assert spec.wavelength_nm == [350.0, 400.0]
        # Converted to fraction
        assert spec.eqe_fraction == [0.5, 0.8]
        assert "wavelength range too narrow" in spec.warnings
        assert "too few points" in spec.warnings

def test_eqe_spectrum_reader_fraction_micron():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsv_file = Path(tmpdir) / "dev2_eqe.tsv"
        # Wavelengths in microns, EQE is fraction
        tsv_file.write_text("lambda\tipce\n0.4\t0.75\n0.5\t0.80\n", encoding="utf-8")
        
        spec = read_eqe_spectrum_file(str(tsv_file))
        assert spec.wavelength_nm == [400.0, 500.0]  # Converted to nm!
        assert spec.eqe_fraction == [0.75, 0.80]
        assert "wavelength converted from um to nm" in spec.warnings
