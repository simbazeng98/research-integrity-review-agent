from __future__ import annotations

import tempfile
from pathlib import Path
from integrity_agent.domains.photovoltaics.raw_measurements.jv_curve_reader import read_jv_curve_file

def test_jv_curve_reader_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "dev1_fwd.csv"
        csv_file.write_text("V,Jsc (mA/cm2)\n-0.1,-22.1\n0.0,-22.0\n1.1,0.0\n", encoding="utf-8")
        
        curve = read_jv_curve_file(str(csv_file))
        assert curve.scan_direction == "forward"
        assert curve.device_id_guess == "dev1"
        assert curve.voltage_v == [-0.1, 0.0, 1.1]
        assert curve.current_density_ma_cm2 == [-22.1, -22.0, 0.0]
        assert not curve.warnings

def test_jv_curve_reader_tsv():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsv_file = Path(tmpdir) / "dev2_rev.tsv"
        tsv_file.write_text("voltage\tcurrent density\n1.1\t0.0\n0.0\t-20.0\n", encoding="utf-8")
        
        curve = read_jv_curve_file(str(tsv_file))
        assert curve.scan_direction == "reverse"
        assert curve.device_id_guess == "dev2"
        assert curve.voltage_v == [1.1, 0.0]
        assert curve.current_density_ma_cm2 == [0.0, -20.0]

def test_jv_curve_reader_whitespace_txt():
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "dev3_unknown.txt"
        txt_file.write_text("bias   current\n-0.1   -2.21\n0.0   -2.20\n", encoding="utf-8")
        
        # Test current to current-density conversion
        metadata = {"active_area_cm2": 0.1}
        curve = read_jv_curve_file(str(txt_file), metadata)
        assert curve.scan_direction == "unknown"
        # Current in mA / area = -2.20 / 0.1 = -22.0
        assert len(curve.current_density_ma_cm2) == 2
        assert abs(curve.current_density_ma_cm2[0] - (-22.1)) < 1e-5
        assert abs(curve.current_density_ma_cm2[1] - (-22.0)) < 1e-5
        assert any("Converted current to current density" in w for w in curve.warnings)

def test_jv_curve_reader_missing_headers():
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "no_headers.txt"
        txt_file.write_text("-0.1 -22.1\n0.0 -22.0\n", encoding="utf-8")
        
        curve = read_jv_curve_file(str(txt_file))
        assert curve.voltage_v == [-0.1, 0.0]
        assert curve.current_density_ma_cm2 == [-22.1, -22.0]
