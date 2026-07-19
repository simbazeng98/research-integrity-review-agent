from __future__ import annotations

import pytest
from pydantic import ValidationError

from integrity_agent.core.claims import AtomicClaim


def _claim(**overrides):
    record = {
        "claim_id": "claim-trpl-main-1",
        "claim_type": "trpl_fit",
        "value": "1.1702",
        "unit": "μs",
        "device_variant": "wide-bandgap",
        "sample_id": "device-A",
        "measurement_context": "TRPL biexponential fit",
        "source_document": "main",
        "source_version": "publisher-v1",
        "location": "Page 5, paragraph 2",
        "source_hash": "sha256:toy-source-hash",
        "human_confirmed": True,
    }
    record.update(overrides)
    return record


def test_atomic_claim_requires_device_variant():
    record = _claim()
    del record["device_variant"]

    with pytest.raises(ValidationError, match="device_variant"):
        AtomicClaim.model_validate(record)


def test_atomic_claim_rejects_incompatible_unit():
    with pytest.raises(ValidationError, match="unit"):
        AtomicClaim.model_validate(_claim(claim_type="pce", value=22.5, unit="kelvin"))


def test_atomic_claim_normalizes_units_deterministically_without_losing_source_evidence():
    claim = AtomicClaim.model_validate(_claim())

    assert claim.normalized_value == pytest.approx(1170.2)
    assert claim.normalized_unit == "ns"
    assert claim.location == "Page 5, paragraph 2"
    assert claim.source_hash == "sha256:toy-source-hash"

    record = claim.to_record()
    assert record["value"] == "1.1702"
    assert record["unit"] == "μs"
    assert record["normalized_value"] == pytest.approx(1170.2)
    assert record["normalized_unit"] == "ns"


def test_atomic_claim_comparison_key_contains_all_context_dimensions():
    claim = AtomicClaim.model_validate(_claim())

    assert claim.comparison_key == (
        "trpl_fit",
        "wide-bandgap",
        "device-A",
        "TRPL biexponential fit",
        "publisher-v1",
    )
    assert claim.comparison_key_dict() == {
        "claim_type": "trpl_fit",
        "device_variant": "wide-bandgap",
        "sample_id": "device-A",
        "measurement_context": "TRPL biexponential fit",
        "source_version": "publisher-v1",
    }


def test_missing_sample_identity_is_explicit_context_not_a_schema_default():
    claim = AtomicClaim.model_validate(_claim(sample_id=None))

    assert claim.sample_id is None
    assert claim.has_complete_comparison_context is False


def test_unconfirmed_claim_is_draft_candidate_and_not_finding_eligible():
    claim = AtomicClaim.model_validate(_claim(human_confirmed=False))

    assert claim.record_status == "draft_candidate"
    assert claim.eligible_for_finding is False
    assert claim.to_record()["eligible_for_finding"] is False


def test_claim_rejects_private_absolute_source_location():
    private_location = f"{chr(67)}:{chr(92)}private{chr(92)}paper.pdf:page=5"
    with pytest.raises(ValidationError, match="private/local path"):
        AtomicClaim.model_validate(_claim(location=private_location))

    posix_private_location = "/" + "home/person/paper.pdf:page=5"
    with pytest.raises(ValidationError, match="private/local path"):
        AtomicClaim.model_validate(_claim(location=posix_private_location))
