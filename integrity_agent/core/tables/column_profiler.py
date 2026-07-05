from __future__ import annotations

import re
from collections import Counter
from integrity_agent.core.tables.table_schema import ColumnProfile


def is_missing(val: str) -> bool:
    """Check if a string value represents a missing data cell."""
    val_clean = val.strip().lower()
    return val_clean in ["", "na", "n/a", "nan", "null", "none"]


def parse_float(val: str) -> float | None:
    """Attempt to parse a string as a float."""
    try:
        return float(val)
    except ValueError:
        return None


def parse_int(val: str) -> int | None:
    """Attempt to parse a string as an integer."""
    try:
        # Avoid float-like integers like "1.0" in direct int conversion
        if "." in val:
            f = float(val)
            if f.is_integer():
                return int(f)
            return None
        return int(val)
    except ValueError:
        return None


def get_decimal_places(val_str: str) -> int:
    """Get the number of decimal places in a numeric string representation."""
    val_str = val_str.strip()
    if "." in val_str:
        # Count only digits after the decimal point
        parts = val_str.split(".")
        if len(parts) == 2:
            # Strip trailing units or spaces if any
            dec_part = re.sub(r"[^\d]", "", parts[1])
            return len(dec_part)
    return 0


def get_terminal_digit(val_str: str) -> int | None:
    """Extract the last digit character from a numeric string."""
    digits = [c for c in val_str if c.isdigit()]
    if digits:
        return int(digits[-1])
    return None


def profile_column(column_name: str, values: list[str]) -> ColumnProfile:
    """Analyze a list of column string values and compile a ColumnProfile."""
    warnings: list[str] = []
    total_count = len(values)

    non_missing_values = [v.strip() for v in values if not is_missing(v)]
    missing_count = total_count - len(non_missing_values)
    unique_count = len(set(non_missing_values))

    numeric_values: list[float] = []
    numeric_strings: list[str] = []
    integer_count = 0
    float_count = 0

    for v in non_missing_values:
        f_val = parse_float(v)
        if f_val is not None:
            numeric_values.append(f_val)
            numeric_strings.append(v)
            i_val = parse_int(v)
            if i_val is not None:
                integer_count += 1
            else:
                float_count += 1

    numeric_count = len(numeric_values)

    # Infer type
    if not non_missing_values:
        inferred_type = "string"
    elif numeric_count == len(non_missing_values):
        if integer_count == numeric_count:
            inferred_type = "integer"
        else:
            inferred_type = "float"
    elif numeric_count > 0:
        inferred_type = "mixed"
    else:
        inferred_type = "string"

    # Analyze decimal places and terminal digits for numeric values
    decimal_places: dict[int, int] = {}
    terminal_digits: dict[int, int] = {}

    if numeric_count > 0:
        dec_counter = Counter(get_decimal_places(s) for s in numeric_strings)
        decimal_places = dict(dec_counter)

        term_list = []
        for s in numeric_strings:
            td = get_terminal_digit(s)
            if td is not None:
                term_list.append(td)
        term_counter = Counter(term_list)
        terminal_digits = dict(term_counter)

    # Unit hint from column name
    unit_hint = None
    lower_name = column_name.lower()
    if "ma/cm2" in lower_name or "ma/cm^2" in lower_name:
        unit_hint = "mA/cm2"
    elif "%" in lower_name:
        unit_hint = "%"
    elif "mv" in lower_name:
        unit_hint = "mV"
    elif "ma" in lower_name:
        unit_hint = "mA"
    elif "nm" in lower_name:
        unit_hint = "nm"
    elif "ev" in lower_name:
        unit_hint = "eV"
    elif "v" in lower_name:
        unit_hint = "V"

    # Precision hint (based on maximum decimal places)
    precision_hint = None
    if decimal_places:
        max_dec = max(decimal_places.keys())
        precision_hint = float(10 ** (-max_dec))

    return ColumnProfile(
        column_name=column_name,
        inferred_type=inferred_type,
        numeric_count=numeric_count,
        missing_count=missing_count,
        unique_count=unique_count,
        decimal_places_observed=decimal_places,
        terminal_digits_observed=terminal_digits,
        unit_hint=unit_hint,
        precision_hint=precision_hint,
        warnings=warnings,
    )
