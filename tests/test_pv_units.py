from __future__ import annotations

from integrity_agent.domains.photovoltaics.units import (
    normalize_voc, normalize_jsc, normalize_ff, normalize_pce, normalize_area, normalize_bandgap
)

def test_normalize_voc():
    # standard V
    val, warnings = normalize_voc(1.10, "v")
    assert val == 1.10
    assert not warnings

    # mV conversion
    val, warnings = normalize_voc(1100, "mv")
    assert val == 1.10
    assert not warnings

    # Ambiguous large Voc warning
    val, warnings = normalize_voc(1200, None)
    assert val == 1200.0
    assert len(warnings) == 1
    assert "Assume" in warnings[0] or "mV" in warnings[0]

def test_normalize_jsc():
    # standard
    val, warnings = normalize_jsc(22.0, "ma/cm2")
    assert val == 22.0
    assert not warnings

    # A/m2 conversion: 1 A/m2 = 0.1 mA/cm2
    val, warnings = normalize_jsc(200.0, "a/m2")
    assert val == 20.0
    assert len(warnings) == 1

    # A/cm2 conversion: 1 A/cm2 = 1000 mA/cm2
    val, warnings = normalize_jsc(0.02, "a/cm2")
    assert val == 20.0
    assert len(warnings) == 1

def test_normalize_ff():
    # percentage
    val, unit, warnings = normalize_ff(75.0, "%")
    assert val == 0.75
    assert unit == "%"
    assert not warnings

    # fraction
    val, unit, warnings = normalize_ff(0.75, "fraction")
    assert val == 0.75
    assert unit == "fraction"
    assert not warnings

    # auto-detect percent
    val, unit, warnings = normalize_ff(75.0, None)
    assert val == 0.75
    assert unit == "%"
    assert len(warnings) == 1

    # implausible
    val, unit, warnings = normalize_ff(150.0, None)
    assert val == 150.0
    assert len(warnings) == 1

def test_normalize_pce():
    # percentage
    val, warnings = normalize_pce(18.15, "%")
    assert val == 18.15
    assert not warnings

    # fraction conversion
    val, warnings = normalize_pce(0.1815, "fraction")
    assert val == 18.15
    assert len(warnings) == 1

def test_normalize_area():
    # cm2
    val, warnings = normalize_area(0.1, "cm2")
    assert val == 0.1
    assert not warnings

    # mm2 conversion
    val, warnings = normalize_area(10, "mm2")
    assert val == 0.1
    assert len(warnings) == 1

def test_normalize_bandgap():
    # eV
    val, warnings = normalize_bandgap(1.60, "ev")
    assert val == 1.60
    assert not warnings

    # nm warning
    val, warnings = normalize_bandgap(780, "nm")
    assert val == 780.0
    assert len(warnings) == 1
