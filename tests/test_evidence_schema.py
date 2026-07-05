from integrity_agent.core.evidence.schema import (
    EvidenceItem,
    Finding,
    ManualVerification,
    RiskLevel,
)


def test_finding_serializes_to_ledger_record():
    finding = Finding(
        finding_id="F001",
        type="image_similarity",
        title="Toy duplicated microscopy panel candidate",
        risk=RiskLevel.MEDIUM,
        summary="Fig. 1a and Fig. 2b share a toy repeated pattern.",
        evidence=[
            EvidenceItem(
                source="examples/toy_case.md",
                location="Fig. 1a vs Fig. 2b",
                quote="toy repeated pattern",
            )
        ],
        manual_verification=ManualVerification(
            needed=True,
            requests=["Provide original, unprocessed toy source images."],
        ),
        alternative_explanations=["Shared control shown with explicit labeling."],
    )

    record = finding.to_ledger_record()

    assert record["finding_id"] == "F001"
    assert record["risk"] == "medium"
    assert record["needs_manual_review"] is True
    assert record["evidence"][0]["location"] == "Fig. 1a vs Fig. 2b"
    assert record["alternative_explanations"] == [
        "Shared control shown with explicit labeling."
    ]
