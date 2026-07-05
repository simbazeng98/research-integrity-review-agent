from __future__ import annotations

from integrity_agent.core.tables.column_profiler import profile_column


def test_profile_integer_column():
    vals = ["1", "2", "3", "3", "", "NA"]
    profile = profile_column("count (nm)", vals)
    
    assert profile.inferred_type == "integer"
    assert profile.numeric_count == 4
    assert profile.missing_count == 2
    assert profile.unique_count == 3
    assert profile.unit_hint == "nm"
    assert profile.decimal_places_observed == {0: 4}
    assert profile.precision_hint == 1.0
    # Digits are 1, 2, 3, 3. Counter: {1: 1, 2: 1, 3: 2}
    assert profile.terminal_digits_observed == {1: 1, 2: 1, 3: 2}


def test_profile_float_column():
    vals = ["1.23", "2.50", "3.0", "NaN"]
    profile = profile_column("voltage (V)", vals)
    
    assert profile.inferred_type == "float"
    assert profile.numeric_count == 3
    assert profile.missing_count == 1
    assert profile.unit_hint == "V"
    # decimal places for 1.23 is 2, 2.50 is 2, 3.0 is 1.
    assert profile.decimal_places_observed == {2: 2, 1: 1}
    assert profile.precision_hint == 0.01
    # terminal digits for 1.23 -> 3, 2.50 -> 0, 3.0 -> 0.
    assert profile.terminal_digits_observed == {3: 1, 0: 2}


def test_profile_mixed_column():
    vals = ["1.2", "hello", "3.4"]
    profile = profile_column("mixed_col", vals)
    
    assert profile.inferred_type == "mixed"
    assert profile.numeric_count == 2
    assert profile.missing_count == 0
    assert profile.unique_count == 3
