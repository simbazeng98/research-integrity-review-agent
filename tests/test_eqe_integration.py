from __future__ import annotations

from integrity_agent.domains.photovoltaics.raw_measurements.schema import EQESpectrum
from integrity_agent.domains.photovoltaics.raw_measurements.eqe_integration import integrate_eqe_jsc

def test_integrate_eqe_jsc():
    # Simple toy spectrum: 300 to 1200 nm, EQE fraction = 0.8
    # Ref spectrum: constant 1.0 irradiance
    ref_spectrum = [
        (300.0, 1.0),
        (500.0, 1.0),
        (800.0, 1.0),
        (1200.0, 1.0)
    ]
    
    spec = EQESpectrum(
        spectrum_id="toy-spec",
        source_file="toy.csv",
        wavelength_nm=[300.0, 600.0, 1200.0],
        eqe_fraction=[0.8, 0.8, 0.8],
        device_id_guess="dev1"
    )
    
    result = integrate_eqe_jsc(spec, ref_spectrum)
    assert result.integrated_jsc_ma_cm2 > 0.0
    assert 20.0 < result.integrated_jsc_ma_cm2 < 50.0
    assert "sparse wavelength grid" in result.warnings
