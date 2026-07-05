from integrity_agent.detectors.registry import (
    get_detector,
    run_detector,
    register_detector,
    list_loaded_detectors,
)
from integrity_agent.detectors.numeric.fixed_delta import detect_fixed_delta
from integrity_agent.detectors.numeric.terminal_digit import detect_terminal_digits
from integrity_agent.detectors.metadata.crossref_retraction_check import check_retraction_metadata
from integrity_agent.detectors.metadata.retraction_mock import check_mock_metadata

# Statically pre-register active detectors
register_detector("numeric_fixed_delta_between_columns", detect_fixed_delta)
register_detector("numeric_terminal_digit_anomaly", detect_terminal_digits)
register_detector("retraction_metadata_check", check_retraction_metadata)

__all__ = [
    "get_detector",
    "run_detector",
    "register_detector",
    "list_loaded_detectors",
    "detect_fixed_delta",
    "detect_terminal_digits",
    "check_retraction_metadata",
    "check_mock_metadata",
]
